from backend.app.assessment import JudgmentBatch, LLMJudgment, needs_branch_review, validate_batch
from backend.app.intake import build_profile
from backend.app.schemas import Criterion, IntakeAnswer, IntakeSubmission, TrialRecord

DESC = 'Patient has cystic fibrosis. Age 24.'


def _setup(text, kind='inclusion'):
    profile = build_profile(IntakeSubmission(answers={
        'condition': IntakeAnswer(state='answered', value='cystic fibrosis'),
        'age': IntakeAnswer(state='answered', value='24')}))
    trial = TrialRecord(nct_id='NCT00000001', title='t', conditions=['Cystic Fibrosis'], status='RECRUITING', phase=[],
                        locations=[], eligibility_text=text, brief_summary='', source='clinicaltrials.gov',
                        url='https://clinicaltrials.gov/study/NCT00000001')
    crit = Criterion(id='IN-1' if kind == 'inclusion' else 'EX-1', kind=kind, text=text, source_text=text)
    return profile, trial, crit


def _verdict(text, status, kind='inclusion'):
    profile, trial, crit = _setup(text, kind)
    ev = [profile.description[:12]]
    batch = JudgmentBatch(assessments=[LLMJudgment(criterion_id=crit.id, status=status, patient_evidence=ev, explanation='x')])
    return validate_batch(profile, trial, [crit], batch)[0]


def test_or_clause_not_met_goes_to_review():
    r = _verdict('Participated in Part A OR less than 7 years of age at the first study visit.', 'not_met')
    assert r.status == 'clinical_review' and not r.verified_evidence and r.patient_evidence == []


def test_or_clause_met_is_kept():
    assert _verdict('Aged 18 or older OR enrolled in Part A', 'met').status == 'met'


def test_future_intent_is_never_decided_from_profile_facts():
    for status in ('met', 'not_met'):
        r = _verdict('Physician intent to prescribe ivacaftor or elexacaftor/tezacaftor/ivacaftor.', status)
        assert r.status == 'clinical_review'


def test_plain_clause_still_decided():
    r = _verdict('Documentation of a CF diagnosis.', 'met')
    assert r.status == 'met' and r.verified_evidence


def test_branch_helper():
    c = Criterion(id='IN-1', kind='inclusion', text='a or b', source_text='a or b')
    assert needs_branch_review(c, 'not_met') and not needs_branch_review(c, 'met') and not needs_branch_review(c, 'unknown')
