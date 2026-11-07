from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator
import re

class Mode(str, Enum):
    replay = 'replay'
    live = 'live'

class Fact(BaseModel):
    field: str
    value: str
    evidence: str
    source: Literal['explicit', 'user_corrected'] = 'explicit'

class PatientProfile(BaseModel):
    description: str = Field(min_length=10, max_length=3000)
    age: int | None = Field(default=None, ge=0, le=120)
    diagnosis: str | None = None
    stage: str | None = None
    biomarkers: list[str] = Field(default_factory=list)
    treatments: list[str] = Field(default_factory=list)
    location: str | None = None
    facts: list[Fact] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    synthetic: Literal[True] = True

class ProfileRequest(BaseModel):
    description: str = Field(min_length=10, max_length=3000)
    mode: Mode = Mode.replay

class TrialRecord(BaseModel):
    nct_id: str
    title: str
    conditions: list[str] = Field(default_factory=list)
    status: str = "UNKNOWN"
    phase: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    eligibility_text: str = ""
    brief_summary: str = ""
    updated: str | None = None
    url: str | None = None
    source: Literal['clinicaltrials.gov', 'synthetic_fixture']
    retrieved_at: str | None = None
    relevance_score: float = 0
    @field_validator('nct_id')
    @classmethod
    def validate_id(cls,v: str) -> str:
        if not re.fullmatch(r'(?:NCT\d{8}|DEMO-\d{3})',v):
            raise ValueError('Invalid trial identifier')
        return v

class Criterion(BaseModel):
    id: str
    kind: Literal['inclusion', 'exclusion']
    text: str
    source_text: str

class CriterionAssessment(BaseModel):
    criterion_id: str
    status: Literal['met','not_met','unknown','clinical_review']
    exclusion_triggered: bool | None = None
    explanation: str = ''
    patient_evidence: list[str] = Field(default_factory=list)
    question_for_doctor: str | None = None
    verified_evidence: bool = False

class SkepticFinding(BaseModel):
    criterion_id: str
    independent_status: Literal['met','not_met','unknown','clinical_review']
    exclusion_triggered: bool | None = None
    explanation: str = ''
    disagreement: bool = False

class TrialAssessment(BaseModel):
    nct_id: str
    criteria: list[Criterion]
    assessments: list[CriterionAssessment]
    skeptic: list[SkepticFinding] = Field(default_factory=list)
    summary: Literal['potential_match','needs_information','identified_conflict','clinical_review']
    unresolved: list[str] = Field(default_factory=list)
    provenance: Literal['live_llm','synthetic_replay']

class SearchRequest(BaseModel):
    profile: PatientProfile
    mode: Mode = Mode.replay
    limit: int = Field(default=10,ge=1,le=40)

class SearchResponse(BaseModel):
    mode: Mode
    trials: list[TrialRecord]
    total_returned: int
    retrieval_method: str
    disclaimer: str = 'Research demonstration only. Relevance does not imply eligibility.'

class AssessRequest(BaseModel):
    profile: PatientProfile
    trial: TrialRecord
    mode: Mode = Mode.replay

class AnalysisRequest(BaseModel):
    profile: PatientProfile
    mode: Mode = Mode.replay
    limit: int = Field(default=3,ge=1,le=5)

class AnalysisResponse(BaseModel):
    mode: Mode
    profile: PatientProfile
    trials: list[TrialRecord]
    assessments: list[TrialAssessment]
    timings_ms: dict[str,float] = Field(default_factory=dict)
    disclaimer: str = 'Synthetic research demonstration, not clinical advice or confirmed eligibility.'

class TrialChange(BaseModel):
    nct_id: str
    changed_fields: list[str]
    previous_updated: str | None = None
    current_updated: str | None = None

class ExperimentRun(BaseModel):
    run_id: str
    dataset: str
    model: str
    algorithm: str
    sample_size: int
    measured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: dict[str,float] = Field(default_factory=dict)
