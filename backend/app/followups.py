"""MVP 1.5-B: bounded, source-grounded follow-up planning.

Only explicitly recognized requirement phrasing is mapped to patient-fact keys.
Unrecognized clinical criteria are surfaced for human review, never inferred.
One canonical fact key groups equivalent questions across multiple trial records.
This module DOES NOT make eligibility judgments, persist answers, or invoke an LLM.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from .criteria import extract_criteria
from .schemas import (
    PatientProfile, TrialRecord, FollowupQuestion, FollowupPlan,
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


def answer_state(profile: PatientProfile, key: str) -> str:
    """Whether a particular fact is answered, or needs an update.

    'answered' only means a fact was explicitly provided, NOT that the trial
    requirement is satisfied. Eligibility assessment is independent.
    """
    answer=profile.intake_answers.get(key)
    if answer:
        if answer.state=='answered':
            return 'answered'
        return answer.state
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
    # Generic free-text profiles may have evidence for this explicit presence,
    # but absence cannot be inferred from omission.
    if key=='prior_systemic_chemotherapy' and not profile.intake_answers and re.search(r'\b(?:previously received|prior) chemotherapy\b',profile.description,re.I):
        return 'answered'
    return 'missing'


def build_followup_plan(profile: PatientProfile, trials: list[TrialRecord]) -> FollowupPlan:
    groups: dict[str, list[FollowupCriterionLink]] = {}
    unmapped: list[UnmappedCriterion] = []
    mapped=0
    for trial in trials:
        criteria=extract_criteria(trial.eligibility_text)
        for criterion in criteria:
            if not criterion.source_text or criterion.source_text not in trial.eligibility_text:
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
    for fact_key,links in groups.items():
        state=answer_state(profile,fact_key)
        # An already-documented positive test still cannot confirm that the
        # specific activating EGFR variant is known.
        if fact_key=='egfr_result' and state=='answered':
            known=profile.intake_answers.get('egfr_result')
            if known and known.value=='Positive / detected' and answer_state(profile,'egfr_variant')!='answered':
                fact_key='egfr_variant'
                state=answer_state(profile,fact_key)
            else:
                continue
        elif state=='answered':
            continue
        definition=DEFINITIONS[fact_key]
        distinct_trials=len({x.nct_id for x in links})
        # This is a QUESTION PRIORITY, never an eligibility/match score.
        score=definition.priority*10 + (distinct_trials-1)*12
        questions.append(FollowupQuestion(
            fact_key=fact_key,question=definition.question,explanation=definition.explanation,
            input_type=definition.input_type,options=list(definition.options),
            answer_state=state,priority=score,trial_count=distinct_trials,linked_criteria=links))
    questions.sort(key=lambda q:(-q.priority,q.fact_key))
    return FollowupPlan(questions=questions,reviewed_trial_ids=[t.nct_id for t in trials],
        mapped_criterion_count=mapped,unmapped_criteria=unmapped,
        notice='Question suggestions are grounded in listed criteria, not clinical assessments. Answers are not yet collected or reassessed in Increment 1.5-B.')
