"""MVP 1.5-C: cross-study, self-reported fact reassessment tests."""
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import IntakeSubmission, TrialRecord, IntakeAnswer
from app.intake import build_profile
from app.reassessment import reassess

client=TestClient(app)
IDS=['DEMO-001','DEMO-002','DEMO-003']


def a(value=None,state='answered'):
    return {'state':state,'value':value if state=='answered' else None}


def profile(extra=None):
    answers={'condition':a('non-small cell lung cancer'),'age':a(state='unknown'),
             'previous_treatments':a('chemotherapy'),'egfr_result':a(state='pending')}
    answers.update(extra or {})
    res=client.post('/api/v1/intake/profile',json={'answers':answers,'synthetic':True})
    assert res.status_code==200,res.text
    return res.json()


def review(p,updates=None,ids=IDS,mode='replay'):
    return client.post('/api/v1/intake/reassess',json={'profile':p,'trial_ids':ids,
                       'mode':mode,'updates':updates or {}})


def by_id(assessments):
    return {(a['nct_id'],x['criterion_id']):x for a in assessments for x in a['assessments']}


def test_one_age_answer_changes_three_independent_trial_criteria():
    p=profile()
    r=review(p,{'age':a('42')});assert r.status_code==200,r.text
    body=r.json()
    assert len(body['changed_criteria'])==3
    assert {c['nct_id'] for c in body['changed_criteria']}==set(IDS)
    assert all(c['before']=='unknown' and c['after']=='met' for c in body['changed_criteria'])
    assert body['profile']['age']==42
    assert 'age' not in {q['fact_key'] for q in body['followups']['questions']}
    assert 'age' in {q['fact_key'] for q in body['followups']['completed_questions']}
    assert all(a['provenance']=='deterministic_followup' and not a['skeptic'] for a in body['assessments'])
    assert all(a['summary']!='potential_match' for a in body['assessments'])


def test_one_answer_does_not_change_unrelated_exclusion_or_fake_final_clearance():
    r=review(profile(),{'age':a('42')}); body=r.json()
    c=by_id(body['assessments'])
    assert c['DEMO-002','EX-1']['status']=='met'
    assert next(a for a in body['assessments'] if a['nct_id']=='DEMO-002')['summary']=='identified_conflict'
    assert c['DEMO-001','IN-3']['status']=='unknown'
    assert c['DEMO-001','EX-1']['status']=='unknown'
    assert not body['assessments'][0]['skeptic']


def test_correction_reverses_age_and_reopens_shared_question():
    first=review(profile(),{'age':a('42')}).json()
    r=review(first['profile'],{'age':a('16')})
    assert r.status_code==200,r.text
    b=r.json(); assert b['profile']['age']==16
    assert len(b['changed_criteria'])==3
    assert {d['after'] for d in b['changed_criteria']}=={'not_met'}
    assert 'age' in {q['fact_key'] for q in b['followups']['completed_questions']}
    r=review(b['profile'],{'age':a(state='unknown')});assert r.status_code==200,r.text
    body=r.json();assert body['profile']['age'] is None
    assert 'age' in {q['fact_key'] for q in body['followups']['questions']}
    assert not any(x['status']=='met' for x in by_id(body['assessments']).values() if x['criterion_id']=='IN-1')


def test_age_thresholds_are_independent():
    p=build_profile(IntakeSubmission(answers={'condition':a('sickle cell disease')}))
    trials=[TrialRecord(nct_id='DEMO-007',title='A',source='synthetic_fixture',eligibility_text='Inclusion Criteria:\n- Age 18 years or older'),
            TrialRecord(nct_id='DEMO-008',title='B',source='synthetic_fixture',eligibility_text='Inclusion Criteria:\n- Age 65 years or older')]
    # Test pure rule evaluation on distinct threshold studies without inventing fixture IDs.
    b=reassess(p,trials,{'age':IntakeAnswer(state='answered',value='42')})
    assert [a.assessments[0].status for a in b.assessments]==['met','not_met']
    assert len(b.changed_criteria)==2


def test_pending_biomarker_never_counts_as_negative():
    before=review(profile()).json()
    q=next(x for x in before['followups']['questions'] if x['fact_key']=='egfr_result')
    assert q['answer_state']=='pending'
    assert by_id(before['assessments'])['DEMO-001','IN-3']['status']=='unknown'
    negative=review(before['profile'],{'egfr_result':a('Negative / not detected')}).json()
    assert by_id(negative['assessments'])['DEMO-001','IN-3']['status']=='not_met'
    assert negative['profile']['intake_answers']['egfr_result']['value']=='Negative / not detected'


def test_positive_egfr_requests_specific_variant_but_never_auto_approves():
    first=review(profile(),{'egfr_result':a('Positive / detected')}).json()
    assert by_id(first['assessments'])['DEMO-001','IN-3']['status']=='clinical_review'
    assert 'egfr_variant' in {q['fact_key'] for q in first['followups']['questions']}
    second=review(first['profile'],{'egfr_variant':a('Exon 19 deletion reported')}).json()
    assert 'egfr_variant' not in {q['fact_key'] for q in second['followups']['questions']}
    assert 'egfr_variant' in {q['fact_key'] for q in second['followups']['completed_questions']}
    assert by_id(second['assessments'])['DEMO-001','IN-3']['status']=='clinical_review'
    third=review(second['profile'],{'egfr_result':a('Negative / not detected')}).json()
    assert 'egfr_variant' not in third['profile']['followup_answers']


def test_explicit_no_and_prior_chemotherapy_conflict_is_not_silently_cleared():
    r=review(profile(),{'prior_systemic_chemotherapy':a('No')})
    # Already answered by intake prior-treatment field. No redundant question is authorized.
    assert r.status_code==422
    p=profile({'previous_treatments':a(state='unknown')})
    first=review(p,{'prior_systemic_chemotherapy':a('No')}).json()
    assert by_id(first['assessments'])['DEMO-002','EX-1']['status']=='not_met'
    # If a conflicting treatment history is subsequently supplied, show clinical review.
    from app.schemas import PatientProfile
    x=PatientProfile.model_validate(first['profile'])
    x.intake_answers['previous_treatments']=type(x.intake_answers['condition'])(state='answered',value='chemotherapy')
    b=review(x.model_dump()).json()
    assert by_id(b['assessments'])['DEMO-002','EX-1']['status']=='clinical_review'


def test_allowlist_rejects_unrelated_answers_tampered_sources_and_modes():
    p=profile()
    for changes,ids,mode,code in [({'medical_magic':a('Yes')},IDS,'replay',422),
                                  ({'cftr_result':a('F508del')},IDS,'replay',422),
                                  ({'age':a('140')},IDS,'replay',422),
                                  ({'age':a('forty')},IDS,'replay',422),
                                  ({'age':a('41')},['DEMO-999'],'replay',404),
                                  ({'age':a('41')},['NCT12345678'],'replay',422),
                                  ({'age':a('41')},['DEMO-001'],'live',422)]:
        r=review(p,changes,ids,mode);assert r.status_code==code,(changes,ids,r.status_code,r.text)


def test_canonical_guided_profile_rebuilt_from_answers_not_client_age():
    p=profile({'age':a('42')});p['age']=9;p['diagnosis']='cystic fibrosis'
    b=review(p).json()
    assert b['profile']['age']==42
    assert b['profile']['diagnosis']=='non-small cell lung cancer'


def test_original_demo_remains_independent_of_reassessment():
    from app.replay import sample_profile
    p=sample_profile().model_dump()
    first=client.post('/api/v1/analysis/run',json={'profile':p,'mode':'replay'}).json()
    assert len(first['assessments'])==3
    b=review(p,{'active_uncontrolled_infection':a('No')}).json()
    assert all(a['provenance']=='deterministic_followup' for a in b['assessments'])
    assert all(not a['skeptic'] for a in b['assessments'])
    still=client.post('/api/v1/analysis/run',json={'profile':p,'mode':'replay'}).json()
    assert len(still['assessments'])==3
