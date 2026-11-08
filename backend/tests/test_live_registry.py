"""End-to-end fake-transport tests for the actual, official-API-shaped route.

No live network in CI. Run `python run_local.py --check-live` on a connected
machine to test the real registry; do not report mocks as live API verification.
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import clinicaltrials as ct
from app.schemas import IntakeAnswer
from app.study_criteria import criteria_for_trial, verifies_original_criterion
from app.reassessment import reassess
from app.intake import build_profile
from app.schemas import IntakeSubmission

client=TestClient(app)
IDS=['NCT12345678','NCT12345679','NCT12345680']


def sample(id, age_min='18 Years', age_max='65 Years'):
    return {'protocolSection': {
        'identificationModule':{'nctId':id,'briefTitle':f'Official Study {id}'},
        'statusModule':{'overallStatus':'RECRUITING','studyLastUpdatePostDateStruct':{'date':'2026-11-06'}},
        'conditionsModule':{'conditions':['Sickle Cell Disease']},
        'designModule':{'phases':['PHASE2']},
        'eligibilityModule':{'eligibilityCriteria':'Inclusion Criteria:\n- Clinically documented sickle cell disease with specialized therapy criteria\nExclusion Criteria:\n- Other protocol-specific contraindications',
            'minimumAge':age_min,'maximumAge':age_max},
        'descriptionModule':{'briefSummary':'Research treatment for participants with sickle cell disease.'},
        'contactsLocationsModule':{'locations':[{'city':'Chicago','state':'Illinois','country':'United States'}]},
    }}


def guided(age_state='unknown'):
    age={'state':'answered','value':'29'} if age_state=='answered' else {'state':age_state,'value':None}
    return client.post('/api/v1/intake/profile',json={'answers':{
        'condition':{'state':'answered','value':'sickle cell disease'},
        'age':age},'synthetic':True}).json()


def mock_registry(monkeypatch, fail=False):
    ct._cache.clear()
    seen=[]
    def respond(req:httpx.Request)->httpx.Response:
        seen.append(req)
        if fail:
            return httpx.Response(503,json={'message':'temporarily unavailable'})
        if req.url.path.endswith('/version'):
            return httpx.Response(200,json={'apiVersion':'2.0.5','dataTimestamp':'2026-11-06T10:00:05'})
        if req.url.params.get('query.cond'):
            assert req.url.params['query.cond']=='sickle cell disease'
            assert req.url.params['filter.overallStatus']=='RECRUITING,NOT_YET_RECRUITING'
            assert req.url.params.get('pageSize')=='50'
            return httpx.Response(200,json={'studies':[sample(id) for id in IDS]})
        if req.url.params.get('filter.ids'):
            return httpx.Response(200,json={'studies':[sample(id) for id in req.url.params['filter.ids'].split(',')]})
        if req.url.path.endswith(tuple(IDS)):
            return httpx.Response(200,json=sample(req.url.path.split('/')[-1]))
        return httpx.Response(404)
    real_async=httpx.AsyncClient
    transport=httpx.MockTransport(respond)
    monkeypatch.setattr(ct.httpx,'AsyncClient',lambda **kwargs:real_async(transport=transport,**kwargs))
    return seen


def test_official_registry_status_and_real_recruiting_search(monkeypatch):
    seen=mock_registry(monkeypatch)
    status=client.get('/api/v1/registry/status')
    assert status.status_code==200,status.text
    assert status.json()['data_timestamp']=='2026-11-06T10:00:05'
    profile=guided()
    result=client.post('/api/v1/trials/search',json={'mode':'live','profile':profile,'limit':5})
    assert result.status_code==200,result.text
    body=result.json()
    assert [t['nct_id'] for t in body['trials']]==IDS
    assert body['retrieval_method']=='clinicaltrials_api_v2_bm25'
    assert all(t['source']=='clinicaltrials.gov' and t['url'].startswith('https://clinicaltrials.gov/study/NCT') for t in body['trials'])
    assert all(t['minimum_age']=='18 Years' and t['maximum_age']=='65 Years' for t in body['trials'])
    # Only the public search term and NCT IDs are sent upstream, never any patient facts.
    assert all('29' not in str(req.url) and 'profile' not in str(req.url) for req in seen)
    assert all('x-goog-api-key' not in req.headers for req in seen)


def test_live_followups_and_reassessment_reuse_public_study_cache(monkeypatch):
    seen=mock_registry(monkeypatch)
    p=guided()
    result=client.post('/api/v1/trials/search',json={'mode':'live','profile':p,'limit':5})
    assert result.status_code==200
    assert len(seen)==1  # 3 public studies cached from initial live search
    plan=client.post('/api/v1/intake/followups',json={'mode':'live','profile':p,'trial_ids':IDS})
    assert plan.status_code==200,plan.text
    questions=[q for q in plan.json()['questions'] if q['fact_key']=='age']
    assert len(questions)==1 and questions[0]['trial_count']==3
    assert all(q['criterion_id']=='REG-AGE' for q in questions[0]['linked_criteria'])
    reviewed=client.post('/api/v1/intake/reassess',json={'mode':'live','profile':p,'trial_ids':IDS,
        'updates':{'age':{'state':'answered','value':'29'}}})
    assert reviewed.status_code==200,reviewed.text
    body=reviewed.json()
    assert len(body['changed_criteria'])==3
    assert all(a['summary']!='potential_match' for a in body['assessments'])
    assert len(seen)==1  # no redundant HTTP fetches per answer
    assert all(t['source_text'].startswith('Minimum age:') for q in questions for t in q['linked_criteria'])


def test_age_min_max_source_verified_and_independent():
    adult=ct.parse_study(sample(IDS[0],age_min='18 Years',age_max='65 Years'))
    older=ct.parse_study(sample(IDS[1],age_min='50 Years',age_max='90 Years'))
    only_max=ct.parse_study(sample(IDS[2],age_min='N/A',age_max='65 Years'))
    assert all(verifies_original_criterion(trial,c) for trial in [adult,older,only_max] for c in criteria_for_trial(trial))
    p=build_profile(IntakeSubmission(answers={'condition':{'state':'answered','value':'sickle cell disease'}}))
    b=reassess(p,[adult,older,only_max],{'age':IntakeAnswer(state='answered',value='29')})
    c={a.nct_id:next(x for x in a.assessments if x.criterion_id=='REG-AGE').status for a in b.assessments}
    assert c=={IDS[0]:'met',IDS[1]:'not_met',IDS[2]:'met'}


def test_live_error_is_not_silently_replaced_with_fictional_data(monkeypatch):
    seen=mock_registry(monkeypatch,fail=True)
    p=guided()
    status=client.get('/api/v1/registry/status')
    assert status.status_code==503
    result=client.post('/api/v1/trials/search',json={'mode':'live','profile':p,'limit':5})
    assert result.status_code==502
    assert 'DEMO-' not in result.text
    assert len(seen)==2


def test_missing_registered_ids_return_404_and_are_not_faked(monkeypatch):
    ct._cache.clear()
    real=httpx.AsyncClient
    monkeypatch.setattr(ct.httpx,'AsyncClient',lambda **kwargs:real(transport=httpx.MockTransport(
        lambda req:httpx.Response(200,json={'studies':[]})),**kwargs))
    r=client.post('/api/v1/intake/followups',json={'mode':'live','profile':guided(),
        'trial_ids':['NCT00000001']})
    assert r.status_code==404


@pytest.mark.parametrize('bad',['', 'NCT-SOMETHING','DEMO-001','NCT12345678;DELETE','[cheat]'])
def test_invalid_study_ids_rejected(bad):
    with pytest.raises(ValueError):
        ct.validate_ids([bad])


@pytest.mark.parametrize('bad',['', 'CT[COND]','a','x'*121])
def test_advanced_condition_syntax_not_accepted(bad):
    with pytest.raises(ValueError):
        ct.validate_condition(bad)
