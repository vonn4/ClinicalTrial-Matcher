"""Conservative criterion dependency inventory for agent traceability.

This is NOT a clinical logic interpreter: complex text remains opaque.
Only existing source-verified mappings become executable patient dependencies.
"""
from __future__ import annotations
from dataclasses import dataclass
from .followups import map_criterion
from .study_criteria import criteria_for_trial, verifies_original_criterion
from .schemas import TrialRecord

@dataclass(frozen=True)
class CriterionDependency:
    nct_id: str
    criterion_id: str
    fact_key: str | None
    source_text: str
    source_verified: bool
    interpretation: str # simple or opaque


def dependencies(trials: list[TrialRecord]) -> list[CriterionDependency]:
    output = []
    for trial in trials:
        for c in criteria_for_trial(trial):
            verified = verifies_original_criterion(trial, c)
            key = map_criterion(c.source_text, c.kind) if verified else None
            output.append(CriterionDependency(trial.nct_id,c.id,key,c.source_text,verified,
                            'simple' if key else 'opaque'))
    return output


def affected_criteria(trials: list[TrialRecord], fact_key: str) -> list[tuple[str,str]]:
    return [(d.nct_id,d.criterion_id) for d in dependencies(trials)
            if d.source_verified and d.fact_key == fact_key]
