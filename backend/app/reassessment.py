"""MVP 1.5-C: bounded, deterministic evidence review after shared answers.

This is NOT an eligibility decision, a medical verification, or an AI skeptic.
Only allowlisted source wording is evaluated; all other requirements stay in
clinical review. Source facts are self-reported synthetic examples.
"""
from __future__ import annotations
import re
from .study_criteria import criteria_for_trial, verifies_original_criterion
from .followups import DEFINITIONS, answer_state, map_criterion, validated_followup, build_followup_plan
from .intake import profile_from_guided_or_text
from .schemas import (
    IntakeAnswer, PatientProfile, TrialRecord, Criterion, CriterionAssessment,
    TrialAssessment, ReassessmentResponse, CriterionDelta,
)

SIMPLE_EXCLUSIONS = {
    'active_uncontrolled_infection', 'prior_systemic_chemotherapy',
    'autoimmune_immunosuppression', 'prior_stem_cell_transplant',
    'recent_lung_transplant',
}


def explicit_answer(profile: PatientProfile, key: str) -> tuple[str | None, str | None]:
    """Return value and transparent self-report evidence (never a verified medical record)."""
    answer = profile.followup_answers.get(key) or profile.intake_answers.get(key)
    if answer:
        if answer.state != 'answered':return None, None
        fact=next((f for f in profile.facts if f.field==key and f.value==answer.value), None)
        evidence=fact.evidence if fact else f'{DEFINITIONS[key].question} — {answer.value}'
        return answer.value,evidence
    if key in {'age','stage'}:
        val=profile.age if key=='age' else profile.stage
        fact=next((f for f in profile.facts if f.field==key),None)
        if val is not None and fact:return str(val),fact.evidence
    if key=='prior_systemic_chemotherapy':
        tx=next((f for f in profile.facts if f.field in {'previous_treatments','treatments'}
                 and re.search(r'\bchemotherapy\b',f.value,re.I)),None)
        if tx:return 'Yes',tx.evidence
        if not profile.intake_answers:
            # The deterministic free-text profiler is limited, and only explicit
            # past chemotherapy wording counts. Its source wording is quoted.
            m=re.search(r'\b(?:previously received|prior) chemotherapy\b',profile.description,re.I)
            if m:return 'Yes',m.group(0)
    return None,None


def review_criterion(profile: PatientProfile,trial: TrialRecord,criterion: Criterion) -> CriterionAssessment:
    key=map_criterion(criterion.source_text,criterion.kind)
    question=DEFINITIONS[key].question if key else None
    if not verifies_original_criterion(trial,criterion):
        return CriterionAssessment(criterion_id=criterion.id,status='clinical_review',
            explanation='The original requirement could not be source-verified.')
    if not key:
        return CriterionAssessment(criterion_id=criterion.id,status='clinical_review',
            explanation='This requirement cannot be interpreted by the restricted rule set. Expert review required.',
            question_for_doctor='Ask the study team how this requirement applies.')

    value,evidence=explicit_answer(profile,key)
    # Conflicting facts must not be silently overridden by a later response.
    if key=='prior_systemic_chemotherapy':
        prior=next((f for f in profile.facts if f.field=='previous_treatments' and
                    re.search(r'\bchemotherapy\b',f.value,re.I)),None)
        if value=='No' and prior:
            return CriterionAssessment(criterion_id=criterion.id,status='clinical_review',
                explanation='Conflicting answers about prior chemotherapy. Confirm the actual treatment history.',
                patient_evidence=[evidence,prior.evidence] if evidence else [prior.evidence],
                verified_evidence=False,question_for_doctor='Confirm whether systemic chemotherapy was previously received.')
    if value is None or evidence is None or value in {"I don't know",'Unsure'}:
        return CriterionAssessment(criterion_id=criterion.id,status='unknown',
            explanation='No definite answer is present. Missing, pending, and not-tested results are not negative results.',
            question_for_doctor=question)

    status='clinical_review'
    explanation='The self-reported answer requires study-team interpretation; no automated clearance is given.'
    t=' '.join(criterion.source_text.lower().split())
    if key=='age':
        try: age=int(value)
        except ValueError: age=-1
        if criterion.id=='REG-AGE':
            lower=re.search(r'minimum age:\s*(\d{1,3})\s+years?',t)
            upper=re.search(r'maximum age:\s*(\d{1,3})\s+years?',t)
            if age>=0 and (lower or upper):
                good=((not lower or age>=int(lower.group(1))) and
                      (not upper or age<=int(upper.group(1))))
                status='met' if good else 'not_met'
        else:
            nums=[int(n) for n in re.findall(r'\b\d{1,3}\b',t)]
            if age>=0 and nums:
                good=(age>=nums[0] and (len(nums)==1 or age<=nums[1]))
                status='met' if good else 'not_met'
        if status in {'met','not_met'}:
            explanation=f'Reported age {age} {"meets" if status=="met" else "does not meet"} this study age requirement (self-reported; not clinical screening).'
    elif key=='stage':
        good=value.lower().strip() in {'stage iii','stage iv'}
        status='met' if good else 'not_met'
        explanation=f'Reported {value} {"matches" if good else "does not match"} the stated Stage III/IV range.'
    elif key=='diagnosis_confirmation':
        if value=='Confirmed':
            status='met'; explanation='Diagnosis reported as clinician-confirmed; not independently verified.'
        else:
            status='unknown';explanation='Diagnosis confirmation cannot be established from this response.'
    elif key=='histology_confirmation':
        if value=='Yes':
            status='met';explanation='Pathology confirmation reported, but the record is not independently checked.'
        elif value=='No':
            status='unknown';explanation='No pathology confirmation reported; ask the study team about documentation.'
        else:status='unknown'
    elif key in SIMPLE_EXCLUSIONS:
        if value in {'Yes','No'}:
            status='met' if value=='Yes' else 'not_met'
            explanation=('The disqualifying condition was reported as present.' if value=='Yes' else
                         'The disqualifying condition was explicitly reported as absent (not independently verified).')
        else:status='unknown'
    elif key=='egfr_result':
        if value=='Negative / not detected':
            status='not_met';explanation='No EGFR mutation detected was reported; the study requires a known activating mutation.'
        elif value=='Positive / detected':
            status='clinical_review';explanation='Positive EGFR testing does not establish the specific activating variant required by the trial.'
        else:
            status='unknown';explanation='An inconclusive result cannot establish a required EGFR activating mutation.'
    elif key=='cftr_result':
        status='clinical_review'
        explanation='The specific CFTR variant and trial requirement need clinician or study-team interpretation.'

    return CriterionAssessment(criterion_id=criterion.id,status=status,
        exclusion_triggered=(status=='met') if criterion.kind=='exclusion' and status in {'met','not_met'} else None,
        explanation=explanation,patient_evidence=[evidence],verified_evidence=(status in {'met','not_met'}),
        question_for_doctor=(question if status in {'unknown','clinical_review'} else None))


def review_trial(profile: PatientProfile,trial: TrialRecord) -> TrialAssessment:
    criteria=criteria_for_trial(trial)
    reviews=[review_criterion(profile,trial,c) for c in criteria]
    conflicts=[c for c,a in zip(criteria,reviews) if
               (c.kind=='inclusion' and a.status=='not_met') or
               (c.kind=='exclusion' and a.exclusion_triggered is True)]
    unclear=[c for c,a in zip(criteria,reviews) if a.status in {'unknown','clinical_review'}]
    if conflicts:summary='identified_conflict'
    elif not criteria or any(a.status=='clinical_review' for a in reviews):summary='clinical_review'
    elif unclear:summary='needs_information'
    else:summary='clinical_review'  # never announce a full match without independent screening
    return TrialAssessment(nct_id=trial.nct_id,criteria=criteria,assessments=reviews,
        skeptic=[],summary=summary,unresolved=[f'{c.id}: requires review' for c in unclear],
        provenance='deterministic_followup')


def reassess(profile: PatientProfile,trials: list[TrialRecord],updates: dict[str, IntakeAnswer]) -> ReassessmentResponse:
    prior=profile_from_guided_or_text(profile)
    before={a.nct_id:a for a in (review_trial(prior,t) for t in trials)}
    plan=build_followup_plan(prior,trials)
    permitted={q.fact_key for q in plan.questions+plan.completed_questions}
    for key,answer in updates.items():
        if key not in permitted:raise ValueError(f'No current study requirement authorizes follow-up: {key}')
        validated_followup(key,answer)
    merged={**prior.followup_answers,**updates}
    # Once an EGFR result changes, the previously entered variant is no longer reliable.
    if 'egfr_result' in updates:
        merged.pop('egfr_variant',None)
    revised=prior.model_copy(update={'followup_answers':merged})
    revised=profile_from_guided_or_text(revised)
    reviewed=[review_trial(revised,t) for t in trials]
    deltas=[]
    for new in reviewed:
        previous={a.criterion_id:a.status for a in before[new.nct_id].assessments}
        for a in new.assessments:
            old=previous.get(a.criterion_id,'unknown')
            if old!=a.status:
                deltas.append(CriterionDelta(nct_id=new.nct_id,criterion_id=a.criterion_id,
                    before=old,after=a.status))
    return ReassessmentResponse(profile=revised,assessments=reviewed,followups=build_followup_plan(revised,trials),
        changed_criteria=deltas,
        notice='Deterministic, partial review of synthetic self-reported facts. No independent skeptic or clinical eligibility decision.')
