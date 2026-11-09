"""Agent 4: blinded independent verification followed by deterministic reconciliation."""
from ..assessment import aggregate
from ..schemas import PatientProfile, TrialRecord, TrialAssessment, SkepticFinding
from ..study_criteria import criteria_for_trial, verifies_original_criterion
from .analyst_agent import model_judgment
from .budget import AgentBudget

async def execute(profile: PatientProfile, trials: list[TrialRecord], primary: list[TrialAssessment],
                  *, model: bool, budget: AgentBudget):
    by_id = {a.nct_id: a for a in primary}
    reconciled: list[TrialAssessment] = []
    checked = 0
    disputes = 0
    failed = 0
    for trial in trials:
        current = by_id[trial.nct_id]
        # Model skeptic sees original facts+requirements ONLY. Primary results
        # are used after the independent call for comparison.
        independently = None
        if model and current.provenance == 'live_llm':
            try:
                independently = await model_judgment(profile, trial, budget, skeptic=True)
            except Exception:
                # Do not erase earlier completed independent reviews. A missing
                # skeptic response is not equivalent to agreement with the analyst.
                failed += 1
        if independently is None:
            # A deterministic source-integrity audit is NOT represented as an
            # independent LLM skeptical judgment. Never clear a model-based study
            # just because the skeptic request was skipped, failed or exhausted.
            evidence_ok = all(verifies_original_criterion(trial, c) for c in criteria_for_trial(trial))
            result = current.model_copy(deep=True)
            if current.provenance == 'live_llm':
                result.summary = 'clinical_review'
                result.unresolved.append('Independent AI skeptic review not completed; cannot confirm preliminary match')
            if not evidence_ok:
                result.summary = 'clinical_review'
                result.unresolved.append('Source-integrity check failed')
            reconciled.append(result)
            continue
        criteria, second = independently
        first = {a.criterion_id: a for a in current.assessments}
        flags = []
        for b in second:
            a = first.get(b.criterion_id)
            disagreement = a is None or a.status != b.status or a.exclusion_triggered != b.exclusion_triggered
            flags.append(SkepticFinding(criterion_id=b.criterion_id, independent_status=b.status,
                        exclusion_triggered=b.exclusion_triggered, explanation=b.explanation,
                        disagreement=disagreement))
            disputes += int(disagreement)
        summary, unresolved = aggregate(criteria, current.assessments, flags)
        result = current.model_copy(deep=True)
        result.skeptic = flags
        result.summary = summary
        result.unresolved = unresolved
        reconciled.append(result)
        checked += 1
    return reconciled, {'model_invoked': checked > 0, 'independent_trials': checked,
                        'model_failures': failed, 'disagreements': disputes, 'source_verified_trials': len(trials)}
