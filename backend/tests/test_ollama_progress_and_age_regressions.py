"""Offline security, accuracy and Ollama integration regression tests.

No outside registry connection, billable request, or live patient data.
"""
import asyncio
import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.assessment import JudgmentBatch, aggregate, validate_batch
from app.criteria import extract_criteria
from app.llm import ModelUnavailable, generate_ollama_json
from app.schemas import PatientProfile, TrialRecord
from app.agents.budget import _calls

TOKEN = 'fake-test-access-token-not-a-secret'
client = TestClient(app)

def profile():
    return PatientProfile(description='Entirely fictional patient, age 39, diagnosed with BBS.',
                          age=39, diagnosis='Bardet-Biedl Syndrome')

def trial(text: str):
    return TrialRecord(nct_id='NCT12345678', title='Synthetic study shape only',
                       conditions=['Bardet-Biedl Syndrome'], status='RECRUITING',
                       source='synthetic_fixture', eligibility_text='Exclusion Criteria:\n- '+text)

def response(status='met', quote='39'):
    return JudgmentBatch.model_validate({'assessments':[{
        'criterion_id':'EX-1','status':status,'exclusion_triggered':status=='met',
        'patient_evidence':[quote], 'explanation':'Model says patient age triggers exclusion',
        'question_for_doctor':None,
    }]})

def test_approval_age_exclusion_not_inferred_from_patient_age():
    """Regression for observed NCT07674290 age-related false conflict."""
    study=trial('patients younger than the age approved for treatment with setmelanotide')
    criteria=extract_criteria(study.eligibility_text)
    for status in ('met','not_met'):
        assessed=validate_batch(profile(),study,criteria,response(status))
        assert len(assessed)==1
        assert assessed[0].status=='clinical_review'
        assert assessed[0].exclusion_triggered is None
        assert not assessed[0].verified_evidence
        assert 'approval age' in assessed[0].explanation.lower()
        assert aggregate(criteria,assessed,[])[0] != 'identified_conflict'

def test_numeric_exclusion_contradiction_is_rejected():
    study=trial('Patients younger than 18 years')
    criteria=extract_criteria(study.eligibility_text)
    out=validate_batch(profile(),study,criteria,response())
    assert out[0].status=='clinical_review'
    assert out[0].exclusion_triggered is None
    assert not out[0].verified_evidence

def test_forged_quote_cannot_trigger_exclusion():
    study=trial('patients younger than the age approved for treatment with setmelanotide')
    criteria=extract_criteria(study.eligibility_text)
    result=validate_batch(profile(),study,criteria,response('met','Invented favorable evidence'))
    assert result[0].status=='unknown'
    assert result[0].exclusion_triggered is None

def test_ollama_local_json_and_blinded_agent_roundtrip(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','ollama')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OLLAMA_MODEL','qwen3:4b')
    monkeypatch.setenv('OLLAMA_BASE_URL','http://127.0.0.1:11434')
    monkeypatch.setenv('OPENAI_ALLOW_BILLABLE','false')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN',TOKEN)
    monkeypatch.setenv('MAX_AGENT_MODEL_CALLS_PER_HOUR','60')
    _calls.clear()
    observed_roles=[]
    original=httpx.AsyncClient
    def respond(req):
        assert req.url.host == '127.0.0.1'
        assert req.url.path == '/api/chat'
        obj=json.loads(req.content)
        assert obj['model']=='qwen3:4b'
        assert obj['stream'] is False and obj['think'] is False
        assert not any('Authorization'==k for k in req.headers.keys())
        body=json.loads(obj['messages'][1]['content'])
        role=body.get('role')
        if role in {'primary_analyst','independent_skeptic'}:
            observed_roles.append(role)
            assert isinstance(obj['format'],dict)
            answer={'assessments':[{
                'criterion_id':criterion['id'],'status':'unknown',
                'exclusion_triggered':None,'patient_evidence':[],
                'explanation':'Fictional record lacks definitive evidence',
                'question_for_doctor':None
            } for criterion in body['criteria']]}
        elif 'questions' in body:
            answer={'ordered_fact_keys':[q['fact_key'] for q in body['questions']]}
        else:
            answer={'concerns':[]}
        return httpx.Response(200,json={'message':{'content':json.dumps(answer)}})
    monkeypatch.setattr('app.llm.httpx.AsyncClient',
                        lambda **kwargs: original(transport=httpx.MockTransport(respond),**kwargs))
    draft=client.post('/api/v1/intake/profile',json={
        'answers':{'condition':{'state':'answered','value':'non-small cell lung cancer'},
                   'age':{'state':'answered','value':'42'}},
        'synthetic':True
    }).json()
    run_id=str(uuid4())
    result=client.post('/api/v1/matching/analyze',
        headers={'X-Live-Access-Token':TOKEN},
        json={'profile':draft,'mode':'replay','depth':'model',
              'study_ids':['DEMO-001'],'max_studies':1,'run_id':run_id})
    assert result.status_code==200,result.text
    body=result.json()
    trace={stage['agent']:stage for stage in body['trace']}
    assert trace['analyst']['execution']=='model'
    assert trace['skeptic']['execution']=='model'
    assert 'primary_analyst' in observed_roles
    assert 'independent_skeptic' in observed_roles
    assert body['assessments'][0]['skeptic']
    assert body['model_calls']>=2
    progress=client.get('/api/v1/matching/progress/'+run_id)
    assert progress.status_code==200
    state=progress.json()
    assert state['completed']==5 and state['status']=='complete'
    assert state['elapsed_seconds']>=0
    assert 'diagnosis' not in progress.text and 'condition' not in progress.text
    assert client.get('/api/v1/matching/progress/'+str(uuid4())).status_code==404

def test_remote_ollama_endpoint_is_rejected_without_network(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OLLAMA_BASE_URL','http://example.com:11434')
    try:
        asyncio.run(generate_ollama_json(model='qwen3:4b',system='Return JSON',payload={}))
    except ModelUnavailable as exc:
        assert 'loopback' in str(exc).lower()
    else:
        raise AssertionError('Remote inference endpoint must not be allowed')

def test_local_ollama_repeat_calls_ignore_cloud_hourly_quota(monkeypatch):
    """No externally imposed per-hour API budget for local inference; 9/run remains."""
    from app.agents.budget import AgentBudget, AgentBudgetExceeded
    monkeypatch.setenv('AI_PROVIDER','ollama')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('MAX_AGENT_MODEL_CALLS_PER_HOUR','1')
    calls=[]
    async def fake(**kwargs):
        calls.append(kwargs)
        return {'ok':True}
    monkeypatch.setattr('app.agents.budget.generate_json',fake)
    async def run():
        budget=AgentBudget(maximum=2)
        for _ in range(2):
            assert await budget.generate(model='qwen3:4b',system='test',payload={}) == {'ok':True}
        try:
            await budget.generate(model='qwen3:4b',system='test',payload={})
        except AgentBudgetExceeded:
            pass
        else:
            raise AssertionError('Per-run cap must still stop a third model call')
    asyncio.run(run())
    assert len(calls)==2
