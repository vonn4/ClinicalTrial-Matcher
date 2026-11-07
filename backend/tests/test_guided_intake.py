"""Increment 1.5-A acceptance tests: synthetic baseline intake and canonical facts."""
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)


def a(value=None, state='answered'):
    return {'state':state,'value':value if state=='answered' else None}


def profile(answers, narrative=''):
    return client.post('/api/v1/intake/profile',json={
        'answers':answers,'narrative':narrative,'synthetic':True})


def test_question_bank_changes_by_condition():
    cancer=client.get('/api/v1/intake/questions',params={'condition':'NSCLC'}).json()['questions']
    sickle=client.get('/api/v1/intake/questions',params={'condition':'sickle cell disease'}).json()['questions']
    cf=client.get('/api/v1/intake/questions',params={'condition':'cystic fibrosis'}).json()['questions']
    assert {'egfr_result','alk_result','stage'} <= {q['id'] for q in cancer}
    assert {'sickle_genotype'} <= {q['id'] for q in sickle}
    assert {'cftr_result'} <= {q['id'] for q in cf}
    assert 'egfr_result' not in {q['id'] for q in sickle}
    assert 'stage' not in {q['id'] for q in cf}
    assert all(q['label'] and q['help'] for q in cancer)


def test_guided_patient_preserves_positive_negative_pending_and_unknown():
    r=profile({
        'condition':a('non-small cell lung cancer'),
        'age':a('42'),
        'stage':a('Stage III'),
        'diagnosis_confirmation':a('Confirmed'),
        'previous_treatments':a('chemotherapy'),
        'egfr_result':a('Negative / not detected'),
        'alk_result':a(state='pending'),
        'current_treatments':a(state='unknown'),
        'location':a('Kansas City, Missouri')
    }, narrative='This fictional patient is worried about their trial options.')
    assert r.status_code==200,r.text
    data=r.json()
    assert data['age']==42 and data['diagnosis']=='non-small cell lung cancer'
    assert data['stage']=='Stage III' and data['treatments']==['chemotherapy']
    assert data['intake_answers']['egfr_result']['value']=='Negative / not detected'
    assert data['intake_answers']['alk_result']=={'state':'pending','value':None}
    assert data['intake_answers']['current_treatments']=={'state':'unknown','value':None}
    assert 'EGFR: Negative / not detected' in data['biomarkers']
    assert all(not item.startswith('ALK:') for item in data['biomarkers'])
    assert 'alk_result: pending' in data['unknowns']
    assert 'current_treatments: unknown' in data['unknowns']
    assert data['intake_story'].startswith('This fictional')
    assert all(f['source']=='guided_answer' for f in data['facts'])


def test_guided_profile_is_rebuilt_and_not_given_fixed_demo_eligibility():
    r=profile({'condition':a('non-small cell lung cancer'),'age':a('42'),
               'stage':a('Stage III'),'previous_treatments':a('chemotherapy'),
               'egfr_result':a(state='unknown')},narrative='Fictional story for human review.')
    data=r.json()
    data['age']=99 # tamper with a field that was derived from explicit answer
    result=client.post('/api/v1/analysis/run',json={
        'mode':'replay','profile':data,'limit':5})
    assert result.status_code==200,result.text
    analyzed=result.json()
    assert analyzed['profile']['age']==42
    assert analyzed['profile']['intake_story']=='Fictional story for human review.'
    assert len(analyzed['trials'])==3
    assert analyzed['assessments']==[]
    assert 'No eligibility' in analyzed['disclaimer']


def test_guided_condition_change_changes_trial_retrieval():
    ids=[]
    for diagnosis in ['sickle cell disease','cystic fibrosis']:
        r=profile({'condition':a(diagnosis),'age':a('29')})
        assert r.status_code==200,r.text
        resp=client.post('/api/v1/analysis/run',json={'mode':'replay','profile':r.json()})
        assert resp.status_code==200,resp.text
        ids.append([t['nct_id'] for t in resp.json()['trials']])
    assert ids==[['DEMO-004'],['DEMO-005']]


def test_unknown_age_not_mistaken_for_zero_or_negative():
    r=profile({'condition':a('sickle cell disease'),'age':a(state='unknown')})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['age'] is None and 'age: unknown' in data['unknowns']


def test_not_tested_not_same_as_negative():
    pending=profile({'condition':a('non-small cell lung cancer'),
                     'egfr_result':a(state='not_tested')})
    assert pending.status_code==200,pending.text
    data=pending.json()
    assert not data['biomarkers']
    assert data['intake_answers']['egfr_result']['state']=='not_tested'


def test_invalid_choices_and_missing_mandatory_condition_are_rejected():
    cases=[
        {'condition':a('sickle cell disease'),'egfr_result':a('Positive / detected')},
        {'condition':a('cystic fibrosis'),'age':a('999')},
        {'condition':a('non-small cell lung cancer'),'egfr_result':a('100% cured')},
        {'age':a('45')},
        {'condition':a('sickle cell disease'),'age':{'state':'unknown','value':'45'}},
        {'condition':a('sickle cell disease'),'mystery_question':a('secret')},
        {'condition':a('sickle cell disease'),'age':a(state='not_tested')},
    ]
    for answers in cases:
        assert profile(answers).status_code==422,answers


def test_explicit_answers_take_precedence_over_conflicting_story():
    r=profile({'condition':a('sickle cell disease'),'age':a('29')},
              narrative='This fictional story mentions a 42-year-old patient with lung cancer.')
    assert r.status_code==200,r.text
    data=r.json()
    assert data['age']==29 and data['diagnosis']=='sickle cell disease'
    assert data['intake_story'].startswith('This fictional story')


def test_guided_intake_rejects_real_patient_mode_flag():
    r=client.post('/api/v1/intake/profile',json={
        'answers':{'condition':a('sickle cell disease')},'synthetic':False})
    assert r.status_code==422


def test_existing_free_text_demo_retained():
    from app.replay import sample_profile
    result=client.post('/api/v1/analysis/run',json={
        'mode':'replay','profile':sample_profile().model_dump()})
    assert result.status_code==200,result.text
    assert len(result.json()['assessments'])==3
