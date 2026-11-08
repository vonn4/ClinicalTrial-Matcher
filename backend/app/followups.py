"""MVP 1.5-B: bounded, source-grounded follow-up planning.

Only explicitly recognized requirement phrasing is mapped to patient-fact keys.
Unrecognized clinical criteria are surfaced for human review, never inferred.
One canonical fact key groups equivalent questions across multiple trial records.
This module DOES NOT make eligibility judgments, persist answers, or invoke an LLM.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from .study_criteria import criteria_for_trial, verifies_original_criterion
from .schemas import (
    PatientProfile, TrialRecord, IntakeAnswer, FollowupQuestion, FollowupPlan,
    FollowupCriterionLink, UnmappedCriterion,
)


@dataclass(frozen=True)
class QuestionDefinition:
    fact_key: str
    question: str
    explanation: str
    input_type: str = 'select'
    options: tuple[str, ...] = ('Yes', 'No', "I don't know")
    priority: int = 0


DEFINITIONS: dict[str, QuestionDefinition] = {
    'age': QuestionDefinition('age', "What is the patient's age in years?", 'A study may specify an age range.', 'number', (), 3),
    'diagnosis_confirmation': QuestionDefinition('diagnosis_confirmation', 'Has a clinician confirmed the diagnosis?', 'The study requires a confirmed diagnosis.', 'select', ('Confirmed', 'Suspected', 'Unsure'), 3),
    'histology_confirmation': QuestionDefinition('histology_confirmation', 'Has the diagnosis been confirmed by pathology (histology)?', 'A pathology-confirmed diagnosis is specifically mentioned.', 'select', ('Yes', 'No', "I don't know"), 4),
    'stage': QuestionDefinition('stage', 'What is the documented disease stage?', 'The study specifies a disease stage.', 'select', ('Stage I','Stage II','Stage III','Stage IV',"I don't know"), 3),
    'egfr_result': QuestionDefinition('egfr_result', 'What is the documented EGFR mutation test result?', 'A study requires EGFR testing; a marker mention is not a positive test.', 'select', ('Positive / detected', 'Negative / not detected', 'Inconclusive', "I don't know"), 4),
    'egfr_variant': QuestionDefinition('egfr_variant', 'Which EGFR variant was identified, and was it documented as activating?', 'A generic positive EGFR result does not establish the specific activating variant.', 'text', (), 4),
    'active_uncontrolled_infection': QuestionDefinition('active_uncontrolled_infection', 'Does the patient currently have an active, uncontrolled infection?', 'This is a study-specific exclusion condition.', 'select', ('Yes', 'No', "I don't know"), 5),
    'prior_systemic_chemotherapy': QuestionDefinition('prior_systemic_chemotherapy', 'Has the patient ever received systemic chemotherapy?', 'This is a study-specific prior-treatment exclusion condition.', 'select', ('Yes', 'No', "I don't know"), 5),
    'autoimmune_immunosuppression': QuestionDefinition('autoimmune_immunosuppression', 'Does the patient have an active autoimmune disease requiring immunosuppressive medication?', 'This combination appears in a study exclusion criterion.', 'select', ('Yes', 'No', "I don't know"), 5),
    'prior_stem_cell_transplant': QuestionDefinition('prior_stem_cell_transplant', 'Has the patient previously received a stem cell transplant?', 'A study identifies prior stem cell transplant as an exclusion.', 'select', ('Yes', 'No', "I don't know"), 5),
    'cftr_result': QuestionDefinition('cftr_result', 'What documented CFTR genetic variant was detected, if known?', 'A trial requires confirmation of a specific CFTR variant.', 'text', (), 4),
    'recent_lung_transplant': QuestionDefinition('recent_lung_transplant', 'Has the patient recently received a lung transplant?', 'A trial identifies a recent lung transplant as an exclusion.', 'select', ('Yes', 'No', "I don't know"), 5),
}


def map_criterion(text: str, kind: str) -> str | None:
    """Conservatively match a small allowlist of source phrasings.

    Complex conjunctions or partial text matches should not be expanded into
    patient-facing questions without a separately reviewed rule.
    """
    t = ' '.join(text.lower().strip().split()).rstrip(' .;')
    if re.fullmatch(r'(?:patient is at least \d{1,3} years old|adult patient at least \d{1,3} years old|adults? \d{1,3} years or older|adults aged \d{1,3} through \d{1,3} years|age \d{1,3} years or older)',t):
        return 'age'
    if re.fullmatch(r'(?:non-small cell lung cancer diagnosis|confirmed sickle cell disease diagnosis|confirmed cystic fibrosis diagnosis)',t):
        return 'diagnosis_confirmation'
    if re.fullmatch(r'minimum age: \d{1,3} years?(?:; maximum age: \d{1,3} years?)?|maximum age: \d{1,3} years?',t):
        return 'age'
    if t=='histologically confirmed non-small cell lung cancer':
        return 'histology_confirmation'
    if re.fullmatch(r'stage (?:[ivx]+|\d+) or (?:[ivx]+|\d+) non-small cell lung cancer',t):
        return 'stage'
    if t=='known egfr activating mutation':
        return 'egfr_result'  # Variant is requested separately when generic positive is known.
    if kind=='exclusion' and t=='active uncontrolled infection':
        return 'active_uncontrolled_infection'
    if kind=='exclusion' and t=='any prior systemic chemotherapy':
        return 'prior_systemic_chemotherapy'
    if kind=='exclusion' and t=='active autoimmune disease requiring immunosuppressive medications':
        return 'autoimmune_immunosuppression'
    if kind=='exclusion' and t=='prior stem cell transplantation':
        return 'prior_stem_cell_transplant'
    if t=='specific cftr variant confirmed on genetic testing':
        return 'cftr_result'
    if kind=='exclusion' and t=='recent lung transplant':
        return 'recent_lung_transplant'
    return None


def validated_followup(key: str, answer: 'IntakeAnswer') -> None:
    """The answer type and allowed values must match the server-owned question bank."""
    if key not in DEFINITIONS:
        raise ValueError(f'Unsupported follow-up fact: {key}')
    definition = DEFINITIONS[key]
    if answer.state in {'pending', 'not_tested'} and key not in {'egfr_result','cftr_result'}:
        raise ValueError(f'Question {key} does not accept state {answer.state}')
    if answer.state != 'answered':
        return
    value = answer.value or ''
    if len(value)>180:
        raise ValueError('Follow-up answer is too long')
    if definition.input_type=='select' and value not in definition.options:
        raise ValueError(f'Invalid answer choice for {key}')
    if definition.input_type=='number':
        if not value.isascii() or not value.isdigit() or not 0<=int(value)<=120:
            raise ValueError('Age must be a whole number from 0 to 120')
    if definition.input_type=='text' and not value.strip():
        raise ValueError('Follow-up text cannot be empty')


def answer_state(profile: PatientProfile, key: str) -> str:
    """Answered is not the same as meeting a particular study requirement."""
    answer=profile.followup_answers.get(key) or profile.intake_answers.get(key)
    if answer: return answer.state
    if key=='age' and profile.age is not None: return 'answered'
    if key=='stage' and profile.stage: return 'answered'
    if key=='diagnosis_confirmation' and any(f.field=='diagnosis_confirmation' for f in profile.facts):
        return 'answered'
    if key=='egfr_result' and any('EGFR:' in marker for marker in profile.biomarkers):
        return 'answered'
    if key=='cftr_result' and any('CFTR:' in marker for marker in profile.biomarkers):
        return 'answered'
    if key=='prior_systemic_chemotherapy' and any(re.search(r'\bchemotherapy\b',f.value,re.I) for f in profile.facts if f.field=='previous_treatments'):
        return 'answered'
    if key=='prior_systemic_chemotherapy' and not profile.intake_answers and re.search(r'\b(?:previously received|prior) chemotherapy\b',profile.description,re.I):
        return 'answered'
    return 'missing'


def build_followup_plan(profile: PatientProfile, trials: list[TrialRecord]) -> FollowupPlan:
    groups: dict[str, list[FollowupCriterionLink]] = {}
    unmapped: list[UnmappedCriterion] = []
    mapped=0
    for trial in trials:
        criteria=criteria_for_trial(trial)
        for criterion in criteria:
            if not verifies_original_criterion(trial, criterion):
                unmapped.append(UnmappedCriterion(nct_id=trial.nct_id,criterion_id=criterion.id,
                    reason='Source evidence was not verified'))
                continue
            fact_key=map_criterion(criterion.source_text,criterion.kind)
            if not fact_key:
                unmapped.append(UnmappedCriterion(nct_id=trial.nct_id,criterion_id=criterion.id,
                    reason='Complex or unsupported requirement; clinical review needed'))
                continue
            mapped+=1
            groups.setdefault(fact_key,[]).append(FollowupCriterionLink(
                nct_id=trial.nct_id,criterion_id=criterion.id,kind=criterion.kind,
                source_text=criterion.source_text))
    questions=[]
    completed=[]
    for fact_key,links in groups.items():
        state=answer_state(profile,fact_key)
        # Generic EGFR positivity does not prove a specific activating variant.
        # Request the variant separately, but never discard a prior answer.
        if fact_key=='egfr_result' and state=='answered':
            known=profile.followup_answers.get('egfr_result') or profile.intake_answers.get('egfr_result')
            if known and known.value=='Positive / detected':
                # Keep the previously supplied EGFR result editable even when
                # a more specific variant question becomes the next step.
                if 'egfr_result' in profile.followup_answers:
                    d=DEFINITIONS['egfr_result']
                    completed.append(FollowupQuestion(fact_key='egfr_result',question=d.question,explanation=d.explanation,
                        input_type=d.input_type,options=list(d.options),answer_state='answered',priority=0,
                        trial_count=len({x.nct_id for x in links}),linked_criteria=links))
                fact_key='egfr_variant'
                state=answer_state(profile,fact_key)
        definition=DEFINITIONS[fact_key]
        trial_count=len({x.nct_id for x in links})
        if state=='answered':
            if fact_key in profile.followup_answers:
                completed.append(FollowupQuestion(fact_key=fact_key,question=definition.question,explanation=definition.explanation,
                    input_type=definition.input_type,options=list(definition.options),answer_state='answered',priority=0,
                    trial_count=trial_count,linked_criteria=links))
            continue
        score=definition.priority*10 + (trial_count-1)*12
        questions.append(FollowupQuestion(
            fact_key=fact_key,question=definition.question,explanation=definition.explanation,
            input_type=definition.input_type,options=list(definition.options),
            answer_state=state,priority=score,trial_count=trial_count,linked_criteria=links))
    questions.sort(key=lambda q:(-q.priority,q.fact_key))
    return FollowupPlan(questions=questions,reviewed_trial_ids=[t.nct_id for t in trials],
        mapped_criterion_count=mapped,unmapped_criteria=unmapped,completed_questions=completed,
        notice='Questions are source-grounded. Answers can be revised; criterion checks remain preliminary, not clinical screening.')
