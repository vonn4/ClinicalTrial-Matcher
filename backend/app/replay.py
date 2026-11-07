"""Versioned synthetic demonstration with exact-profile matching."""
from pathlib import Path
import json
from .schemas import PatientProfile,TrialRecord,TrialAssessment
from .profiling import deterministic_profile
FILE=Path(__file__).parent/'data'/'replay_case.json'

def fixture() -> dict:
    return json.loads(FILE.read_text(encoding='utf-8'))

def sample_profile() -> PatientProfile:
    return deterministic_profile(fixture()['description'])

def verify_replay_profile(profile:PatientProfile) -> None:
    if profile.description.strip()!=fixture()['description'].strip():
        raise ValueError('Replay is fixed to its synthetic example. Restore the sample or choose live mode.')

def replay_trials()->list[TrialRecord]:
    return [TrialRecord.model_validate(x) for x in fixture()['trials']]

def replay_assessments()->list[TrialAssessment]:
    return [TrialAssessment.model_validate(x) for x in fixture()['assessments']]
