"""Agent 3: independent primary criterion assessment against original evidence."""
from ..assessment import JudgmentBatch, PROMPT_COMMON, validate_batch
from ..criteria import extract_criteria
from ..reassessment import review_trial
from ..schemas import PatientProfile, TrialRecord, TrialAssessment
from ..settings import GEMINI_MODEL
from .budget import AgentBudget

MAX_MODEL_CRITERIA = 24

async def model_judgment(profile: PatientProfile, trial: TrialRecord, budget: AgentBudget, *, skeptic: bool = False):
    criteria = extract_criteria(trial.eligibility_text)
    if not criteria or len(criteria) > MAX_MODEL_CRITERIA:
        return None
    system = PROMPT_COMMON
    if skeptic:
        system += (' You are the INDEPENDENT SKEPTIC. Form your own conclusions without seeing the primary analyst. '
                   'Pay particular attention to exclusions, temporal conditions, omitted facts and unsupported positive claims.')
    response = await budget.generate(model=GEMINI_MODEL, system=system, payload={
        'synthetic_patient_description': profile.description,
        'structured_patient': profile.model_dump(exclude={'facts'}),
        'criteria': [{'id': c.id, 'kind': c.kind, 'source_text': c.source_text} for c in criteria],
        'role': 'independent_skeptic' if skeptic else 'primary_analyst',
    })
    batch = JudgmentBatch.model_validate(response)
    return criteria, validate_batch(profile, trial, criteria, batch)

async def execute(profile: PatientProfile, trials: list[TrialRecord], *, model: bool, budget: AgentBudget):
    if not model:
        return [review_trial(profile, t) for t in trials], {'model_invoked': False, 'trials': len(trials)}
    # Each model is bounded to MAX_MODEL_CRITERIA. Complex long inventories stay
    # in the full deterministic clinical-review path instead of being truncated.
    results = []
    handled = 0
    for t in trials:
        outcome = await model_judgment(profile, t, budget)
        if outcome is None:
            results.append(review_trial(profile, t))
            continue
        criteria, assessments = outcome
        from ..assessment import aggregate
        summary, unresolved = aggregate(criteria, assessments, [])
        results.append(TrialAssessment(nct_id=t.nct_id, criteria=criteria, assessments=assessments,
                        skeptic=[], summary=summary, unresolved=unresolved, provenance='live_llm'))
        handled += 1
    return results, {'model_invoked': handled > 0, 'model_reviewed': handled, 'trials': len(trials)}
