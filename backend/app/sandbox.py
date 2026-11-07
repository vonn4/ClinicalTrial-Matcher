"""Interactive, fictional trial discovery. No AI judgments are manufactured.

The canned example has pre-authored educational assessments; edited profiles do not.
"""
import json
from pathlib import Path
from .schemas import PatientProfile, TrialRecord
from .replay import replay_trials, sample_profile
from .ranking import rank_trials

EXTRA = Path(__file__).parent / 'data' / 'sandbox_trials.json'


def is_original_sample(profile: PatientProfile) -> bool:
    """Only the exact server-produced fixture profile may reuse its canned assessments."""
    return profile.model_dump() == sample_profile().model_dump()


def sandbox_search(profile: PatientProfile, limit: int = 10) -> list[TrialRecord]:
    """Return fictional studies for an explicitly recognized diagnosis, never infer eligibility."""
    if not profile.diagnosis:
        return []
    all_trials = replay_trials() + [TrialRecord.model_validate(t) for t in json.loads(EXTRA.read_text(encoding='utf8'))]
    matched = [t for t in all_trials if profile.diagnosis.lower() in ' '.join(t.conditions).lower()]
    return rank_trials(profile, matched)[:limit]
