"""Versioned public contracts for the controlled five-agent workflow."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from ..schemas import Mode, PatientProfile, TrialRecord, TrialAssessment, FollowupPlan, IntakeAnswer, CriterionDelta

AgentName = Literal['profile', 'discovery', 'analyst', 'skeptic', 'clarification']
Execution = Literal['tools', 'model', 'skipped', 'failed']

class AgentTrace(BaseModel):
    agent: AgentName
    execution: Execution
    summary: str
    duration_ms: float = Field(ge=0)
    model_calls: int = Field(default=0, ge=0)
    details: dict[str, int | float | str | bool] = Field(default_factory=dict)

class AgentRunRequest(BaseModel):
    profile: PatientProfile
    mode: Mode = Mode.live
    depth: Literal['tools', 'model'] = 'tools'
    max_studies: int = Field(default=3, ge=1, le=3)
    study_ids: list[str] = Field(default_factory=list, max_length=3)

    @field_validator('study_ids')
    @classmethod
    def distinct_studies(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError('Study IDs must be distinct')
        return value

class AgentClarifyRequest(AgentRunRequest):
    updates: dict[str, IntakeAnswer] = Field(min_length=1, max_length=8)

class AgentRunResponse(BaseModel):
    contract_version: Literal['2.0-A'] = '2.0-A'
    mode: Mode
    profile: PatientProfile
    trials: list[TrialRecord]
    assessments: list[TrialAssessment]
    followups: FollowupPlan
    trace: list[AgentTrace]
    model_calls: int
    candidate_count: int
    changed_criteria: list[CriterionDelta] = Field(default_factory=list)
    notice: str = 'Experimental research navigation using synthetic patient details; not clinical eligibility.'
