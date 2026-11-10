from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re

class Mode(str, Enum):
    replay = 'replay'
    live = 'live'

class Fact(BaseModel):
    field: str
    value: str
    evidence: str
    source: Literal['explicit', 'user_corrected', 'guided_answer'] = 'explicit'

class IntakeAnswer(BaseModel):
    """An explicit answer state. Missing is not equivalent to negative or not tested."""
    state: Literal['answered', 'unknown', 'pending', 'not_tested', 'not_applicable', 'declined']
    value: str | None = None

    @model_validator(mode='after')
    def valid_state(self):
        if self.state == 'answered':
            if self.value is None or not self.value.strip():
                raise ValueError('Answered intake facts require a nonempty value')
            self.value = self.value.strip()
        elif self.value is not None:
            raise ValueError('Non-answered states must not contain a value')
        return self

class IntakeSubmission(BaseModel):
    answers: dict[str, IntakeAnswer] = Field(default_factory=dict, max_length=40)
    narrative: str = Field(default='', max_length=1500)
    synthetic: Literal[True] = True

class IntakeQuestion(BaseModel):
    id: str
    label: str
    help: str
    section: Literal['basics', 'history', 'access']
    input_type: Literal['text', 'number', 'select']
    options: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    required_for_search: bool = False
    placeholder: str = ''

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
    intake_answers: dict[str, IntakeAnswer] = Field(default_factory=dict)
    intake_story: str = Field(default='', max_length=1500)
    followup_answers: dict[str, IntakeAnswer] = Field(default_factory=dict, max_length=24)

class ProfileRequest(BaseModel):
    description: str = Field(min_length=10, max_length=3000)
    mode: Mode = Mode.live

class TrialRecord(BaseModel):
    nct_id: str
    title: str
    conditions: list[str] = Field(default_factory=list)
    status: str = "UNKNOWN"
    phase: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    # Site geo points from official study records, aligned to locations (never inferred).
    location_geopoints: list[tuple[float | None, float | None]] = Field(default_factory=list)
    eligibility_text: str = ""
    brief_summary: str = ""
    updated: str | None = None
    url: str | None = None
    source: Literal['clinicaltrials.gov', 'synthetic_fixture']
    retrieved_at: str | None = None
    minimum_age: str | None = None
    maximum_age: str | None = None
    relevance_score: float = 0
    match_type: Literal['listed_condition','documented_synonym','text_mention'] | None = None
    match_explanation: str = ''
    broad_registry: bool = False
    location_fit: Literal['preferred_city','preferred_state','preferred_radius','outside_radius','other_location','unknown'] = 'unknown'
    location_explanation: str = ''
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
    source: Literal['rules','model'] | None = None

class SkepticFinding(BaseModel):
    criterion_id: str
    independent_status: Literal['met','not_met','unknown','clinical_review']
    exclusion_triggered: bool | None = None
    explanation: str = ''
    disagreement: bool = False

class MatchOverview(BaseModel):
    """Evidence counts for one study. These are not an eligibility score."""
    total: int
    met: int
    not_met: int
    unknown: int
    clinical_review: int
    exclusions_triggered: list[str] = Field(default_factory=list)
    inclusions_failed: list[str] = Field(default_factory=list)
    resolved_by_rules: int = 0
    resolved_by_model: int = 0
    top_missing_questions: list[str] = Field(default_factory=list)

class TrialAssessment(BaseModel):
    nct_id: str
    criteria: list[Criterion]
    assessments: list[CriterionAssessment]
    skeptic: list[SkepticFinding] = Field(default_factory=list)
    summary: Literal['potential_match','needs_information','identified_conflict','clinical_review']
    unresolved: list[str] = Field(default_factory=list)
    provenance: Literal['live_llm','synthetic_replay','deterministic_followup']
    overview: MatchOverview | None = None
    # How this study was actually reviewed; a rules-only study must never look model-reviewed.
    review_basis: Literal['model_and_skeptic', 'model_analyst_only', 'rules_only'] | None = None
    rules_only_reason: str | None = None

class SearchRequest(BaseModel):
    profile: PatientProfile
    mode: Mode = Mode.live
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
    mode: Mode = Mode.live

class AnalysisRequest(BaseModel):
    profile: PatientProfile
    mode: Mode = Mode.live
    limit: int = Field(default=3,ge=1,le=5)

class AnalysisResponse(BaseModel):
    mode: Mode
    profile: PatientProfile
    trials: list[TrialRecord]
    assessments: list[TrialAssessment]
    timings_ms: dict[str,float] = Field(default_factory=dict)
    disclaimer: str = 'Synthetic research demonstration, not clinical advice or confirmed eligibility.'

class FollowupCriterionLink(BaseModel):
    nct_id: str
    criterion_id: str
    kind: Literal['inclusion','exclusion']
    source_text: str

class FollowupQuestion(BaseModel):
    fact_key: str
    question: str
    explanation: str
    input_type: Literal['text','number','select']
    options: list[str] = Field(default_factory=list)
    answer_state: Literal['missing','answered','unknown','pending','not_tested','not_applicable','declined']
    priority: int
    trial_count: int
    linked_criteria: list[FollowupCriterionLink]

class UnmappedCriterion(BaseModel):
    nct_id: str
    criterion_id: str
    reason: str

class FollowupRequest(BaseModel):
    profile: PatientProfile
    mode: Mode = Mode.live
    trial_ids: list[str] = Field(min_length=1, max_length=8)

    @field_validator('trial_ids')
    @classmethod
    def validate_trial_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError('Duplicate study identifiers')
        if any(not re.fullmatch(r'(?:DEMO-\d{3}|NCT\d{8})',v) for v in values):
            raise ValueError('Invalid study identifier')
        return values

class FollowupPlan(BaseModel):
    questions: list[FollowupQuestion]
    reviewed_trial_ids: list[str]
    mapped_criterion_count: int
    unmapped_criteria: list[UnmappedCriterion]
    completed_questions: list[FollowupQuestion] = Field(default_factory=list)
    notice: str

class ReassessmentRequest(FollowupRequest):
    """Client submits self-reported edits; all trial requirements are re-fetched by ID."""
    updates: dict[str, IntakeAnswer] = Field(default_factory=dict, max_length=12)

class CriterionDelta(BaseModel):
    nct_id: str
    criterion_id: str
    before: Literal['met','not_met','unknown','clinical_review']
    after: Literal['met','not_met','unknown','clinical_review']

class ReassessmentResponse(BaseModel):
    profile: PatientProfile
    assessments: list[TrialAssessment]
    followups: FollowupPlan
    changed_criteria: list[CriterionDelta]
    notice: str

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
