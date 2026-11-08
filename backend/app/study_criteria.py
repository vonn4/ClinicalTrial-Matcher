"""Source-verifiable criteria from raw text plus official structured age fields.

A registry age limit exists in eligibilityModule even when eligibilityCriteria
fails to restate it. Keep the two sources distinct in their provenance.
"""
from __future__ import annotations
import re
from .criteria import extract_criteria, validate_evidence
from .schemas import Criterion, TrialRecord


def official_age_clause(trial: TrialRecord) -> str | None:
    if trial.source != 'clinicaltrials.gov':
        return None
    values: list[str] = []
    for label, raw in [('Minimum age', trial.minimum_age), ('Maximum age', trial.maximum_age)]:
        if raw and re.fullmatch(r'\d{1,3}\s+(?:Years?|Months?|Days?)', raw, re.I):
            values.append(f'{label}: {raw}')
    return '; '.join(values) if values else None


def criteria_for_trial(trial: TrialRecord) -> list[Criterion]:
    found = extract_criteria(trial.eligibility_text)
    clause = official_age_clause(trial)
    # Only introduce official structured age if valid and no equivalent recognized
    # free-text age criterion exists. Do not interpret complex requirements here.
    if clause:
        found.append(Criterion(id='REG-AGE', kind='inclusion', text=clause,
                               source_text=clause))
    return found


def verifies_original_criterion(trial: TrialRecord, criterion: Criterion) -> bool:
    if criterion.id == 'REG-AGE':
        return official_age_clause(trial) == criterion.source_text and bool(criterion.source_text)
    return validate_evidence(criterion, trial.eligibility_text)
