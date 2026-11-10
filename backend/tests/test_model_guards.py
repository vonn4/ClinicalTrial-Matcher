from backend.app.assessment import JudgmentBatch, LLMJudgment, needs_branch_review, validate_batch
from backend.app.intake import build_profile
from backend.app.schemas import Criterion, IntakeAnswer, IntakeSubmission, TrialRecord

DESC = 'Patient has cystic fibrosis. Age 24.'


def _setup(text, kind='inclusion'):
    profile = build_profile(IntakeSubmission(answers={
        'condition': IntakeAnswer(state='answered', value='cystic fibrosis'),
        'diagnosis_confirmation': IntakeAnswer(state='answered', value='Confirmed'),
        'age': IntakeAnswer(state='answered', value='24')}))
    trial = TrialRecord(nct_id='NCT00000001', title='t', conditions=['Cystic Fibrosis'], status='RECRUITING', phase=[],
                        locations=[], eligibility_text=text, brief_summary='', source='clinicaltrials.gov',
                        url='https://clinicaltrials.gov/study/NCT00000001')
    crit = Criterion(id='IN-1' if kind == 'inclusion' else 'EX-1', kind=kind, text=text, source_text=text)
    return profile, trial, crit


def _verdict(text, status, kind='inclusion', evidence='age: 24'):
    profile, trial, crit = _setup(text, kind)
    ev = [evidence]
    assert evidence in profile.description
    batch = JudgmentBatch(assessments=[LLMJudgment(criterion_id=crit.id, status=status, patient_evidence=ev, explanation='x')])
    return validate_batch(profile, trial, [crit], batch)[0]


def test_or_clause_not_met_goes_to_review():
    r = _verdict('Participated in Part A OR less than 7 years of age at the first study visit.', 'not_met')
    assert r.status == 'clinical_review' and not r.verified_evidence and r.patient_evidence == []


def test_or_clause_met_is_kept():
    assert _verdict('Aged 18 or older OR enrolled in Part A', 'met', evidence='age: 24').status == 'met'


def test_future_intent_is_never_decided_from_profile_facts():
    for status in ('met', 'not_met'):
        r = _verdict('Physician intent to prescribe ivacaftor or elexacaftor/tezacaftor/ivacaftor.', status)
        assert r.status == 'clinical_review'


def test_plain_clause_still_decided():
    r = _verdict('Documentation of a CF diagnosis.', 'met', evidence='condition: cystic fibrosis')
    assert r.status == 'met' and r.verified_evidence


def test_branch_helper():
    c = Criterion(id='IN-1', kind='inclusion', text='a or b', source_text='a or b')
    assert needs_branch_review(c, 'not_met') and not needs_branch_review(c, 'met') and not needs_branch_review(c, 'unknown')


def test_quote_about_something_else_is_not_evidence():
    # Prior modulator treatment says nothing about which CFTR variants the patient carries.
    profile, trial, crit = _setup('CFTR mutations consistent with FDA labeled indication of highly effective modulator therapy')
    profile = profile.model_copy(update={'description': profile.description + ' previous_treatments: elexacaftor/tezacaftor/ivacaftor.'})
    ev = ['previous_treatments: elexacaftor/tezacaftor/ivacaftor']
    batch = JudgmentBatch(assessments=[LLMJudgment(criterion_id=crit.id, status='met', patient_evidence=ev, explanation='x')])
    r = validate_batch(profile, trial, [crit], batch)[0]
    assert r.status == 'unknown' and not r.verified_evidence and r.patient_evidence == []


def test_related_quotes_are_kept():
    assert _verdict('Aged 19 years or older', 'met', evidence='age: 24').status == 'met'
    assert _verdict('Confirmed diagnosis of CF', 'met', evidence='diagnosis_confirmation: Confirmed').status == 'met'
    assert _verdict('Documentation of a CF diagnosis', 'met', evidence='cystic fibrosis').status == 'met'


def test_unknown_and_review_statuses_are_untouched_by_relevance_check():
    assert _verdict('CFTR mutations consistent with modulator indication', 'unknown', evidence='age: 24').status == 'unknown'


def test_genetic_criteria_need_genetic_evidence_even_if_a_drug_name_is_shared():
    text = ('CFTR mutations consistent with FDA labeled indication of highly effective modulator therapy '
            '(ivacaftor or elexacaftor/tezacaftor/ivacaftor).')
    profile, trial, crit = _setup(text)
    profile = profile.model_copy(update={'description': profile.description + ' previous_treatments: elexacaftor/tezacaftor/ivacaftor. cftr_result: F508del heterozygous.'})

    def verdict(evidence):
        batch = JudgmentBatch(assessments=[LLMJudgment(criterion_id=crit.id, status='met', patient_evidence=[evidence], explanation='x')])
        return validate_batch(profile, trial, [crit], batch)[0].status
    assert verdict('previous_treatments: elexacaftor/tezacaftor/ivacaftor') == 'unknown'
    assert verdict('cftr_result: F508del heterozygous') == 'met'
