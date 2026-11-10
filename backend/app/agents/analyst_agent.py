"""Criterion-level Gemini analysis with structured output, bounded chunks and skeptic budget.

The entire original criterion inventory is always retained. Trials that exceed the
bounded model budget receive explicit deterministic review, never a fabricated pass.
"""
from __future__ import annotations
from math import ceil
from ..assessment import JudgmentBatch, PROMPT_COMMON, validate_batch, aggregate
from ..criteria import extract_criteria
from ..llm import ModelUnavailable
from ..reassessment import review_trial
from ..schemas import PatientProfile, TrialRecord, TrialAssessment
from ..settings import AI_ANALYSIS_MODEL
from .budget import AgentBudget
from .model_errors import explain_model_error

# 30-criterion protocols now use 3 bounded requests per reviewer instead of
# silently skipping everything above the old 24-criterion ceiling.
MAX_MODEL_CRITERIA = 36
CRITERIA_PER_CALL = 12


def call_count(trial: TrialRecord) -> int:
    count = len(extract_criteria(trial.eligibility_text))
    if not count or count > MAX_MODEL_CRITERIA:
        return 0
    return ceil(count / CRITERIA_PER_CALL)


async def model_judgment(profile: PatientProfile, trial: TrialRecord, budget: AgentBudget, *, skeptic: bool = False):
    criteria = extract_criteria(trial.eligibility_text)
    if not criteria or len(criteria) > MAX_MODEL_CRITERIA:
        return None
    system = PROMPT_COMMON + (
        ' Keep explanations under 22 words. Use patient_evidence=[] for unknown or '
        'clinical_review unless a verbatim supporting fragment exists. '
        'Return one assessment for each provided ID, with no additional IDs.'
    )
    if skeptic:
        system += (' You are the INDEPENDENT SKEPTIC. Form your own conclusions without seeing the primary analyst. '
                   'Focus on exclusions, temporal constraints and unsupported positive claims.')
    judgments = []
    for start in range(0, len(criteria), CRITERIA_PER_CALL):
        segment = criteria[start:start + CRITERIA_PER_CALL]
        response = await budget.generate(model=AI_ANALYSIS_MODEL, system=system, payload={
            'synthetic_patient_description': profile.description,
            'structured_patient_facts': [{'field': f.field, 'value': f.value} for f in profile.facts[:35]],
            'unknown_or_pending': profile.unknowns[:30],
            'criteria': [{'id': c.id, 'kind': c.kind, 'source_text': c.source_text} for c in segment],
            'role': 'independent_skeptic' if skeptic else 'primary_analyst',
        })
        batch = JudgmentBatch.model_validate(response)
        requested = {c.id for c in segment}
        # The JSON schema constrains fields; this check blocks fabricated IDs.
        # Missing IDs become unknown in validate_batch, never automatic clearance.
        relevant = [item for item in batch.assessments if item.criterion_id in requested]
        if not relevant:
            raise ModelUnavailable('No source-linked criterion judgments returned')
        judgments.extend(relevant)
    return criteria, validate_batch(profile, trial, criteria,
                                    JudgmentBatch(assessments=judgments))


async def execute(profile: PatientProfile, trials: list[TrialRecord], *, model: bool, budget: AgentBudget):
    if not model:
        return [review_trial(profile, t) for t in trials], {'model_invoked': False, 'trials': len(trials)}
    results = []
    handled = 0
    unsupported = 0
    budget_skips = 0
    failed = 0
    reserved_skeptic = 0
    first_error: dict = {}
    for trial in trials:
        required = call_count(trial)
        if required == 0:
            if len(extract_criteria(trial.eligibility_text)) > MAX_MODEL_CRITERIA:
                unsupported += 1
            results.append(review_trial(profile, trial))
            continue
        # Reserve equal inference capacity for the independent skeptic BEFORE
        # spending the analyst's budget on a later study. Never exceed the cap.
        if budget.calls + reserved_skeptic + 2 * required > budget.maximum:
            budget_skips += 1
            results.append(review_trial(profile, trial))
            continue
        try:
            outcome = await model_judgment(profile, trial, budget)
        except Exception as exc:
            if not first_error:
                first_error = explain_model_error(exc)
            failed += 1
            outcome = None
        if outcome is None:
            results.append(review_trial(profile, trial))
            continue
        criteria, assessments = outcome
        summary, unresolved = aggregate(criteria, assessments, [])
        results.append(TrialAssessment(nct_id=trial.nct_id, criteria=criteria, assessments=assessments,
                        skeptic=[], summary=summary, unresolved=unresolved, provenance='live_llm'))
        handled += 1
        reserved_skeptic += required
    return results, {'model_invoked': handled > 0, 'model_reviewed': handled,
                     'model_failures': failed, 'criteria_limit_skips': unsupported,
                     'budget_skips': budget_skips, 'trials': len(trials), **first_error}
