"""MVP 2.0 integration and agent-boundary tests (no outside network or paid APIs)."""
import asyncio
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.intake import build_profile
from app.schemas import IntakeAnswer, IntakeSubmission, TrialRecord
from app.agents import discovery_agent
from app.agents.budget import AgentBudget, AgentBudgetExceeded

client = TestClient(app)


def patient(condition='non-small cell lung cancer', age=None):
    answers={'condition':IntakeAnswer(state='answered',value=condition)}
    if age is not None:
        answers['age']=IntakeAnswer(state='answered',value=str(age))
    return build_profile(IntakeSubmission(answers=answers,synthetic=True)).model_dump()


def test_capabilities_describe_five_roles_without_claiming_model_use():
    response=client.get('/api/v1/matching/capabilities')
    assert response.status_code==200
    body=response.json()
    assert body['agent_roles']==['profile','discovery','analyst','skeptic','clarification']
    assert body['max_studies']==3
    assert body['max_model_calls_per_run']==9
    assert body['patient_persistence'] is False


def test_all_five_stages_execute_offline_and_disclose_tool_only_behavior(monkeypatch):
    monkeypatch.delenv('ENABLE_LIVE_AI',raising=False)
    response=client.post('/api/v1/matching/analyze',json={
        'mode':'replay','depth':'tools','profile':patient(), 'max_studies':3})
    assert response.status_code==200,response.text
    body=response.json()
    assert [x['agent'] for x in body['trace']]==['profile','discovery','analyst','skeptic','clarification']
    assert all(x['execution']=='tools' for x in body['trace'])
    assert body['model_calls']==0
    assert len(body['trials'])==3
    assert all(a['provenance']=='deterministic_followup' for a in body['assessments'])
    assert all(a['skeptic']==[] for a in body['assessments'])
    ages=[q for q in body['followups']['questions'] if q['fact_key']=='age']
    assert len(ages)==1 and ages[0]['trial_count']==3
    assert 'not clinical eligibility' in body['notice']


def test_live_registry_expansion_deduplicates_real_nct_ids(monkeypatch):
    calls=[]
    sample=TrialRecord(nct_id='NCT12345678',title='Official hypothetical record',
        conditions=['Non-small cell lung cancer'],source='clinicaltrials.gov',
        minimum_age='18 Years',eligibility_text='Inclusion Criteria:\n- Adults 18 years or older',
        brief_summary='Test fixture only',status='RECRUITING')
    async def fake_search(condition,limit=80):
        calls.append(condition)
        return [sample.model_copy(deep=True)]
    monkeypatch.setattr(discovery_agent,'search_trials',fake_search)
    response=client.post('/api/v1/matching/analyze',json={
        'mode':'live','depth':'tools','profile':patient(age=42),'max_studies':3})
    assert response.status_code==200,response.text
    body=response.json()
    assert len(body['trials'])==1
    assert body['trials'][0]['nct_id']=='NCT12345678'
    assert all(t['source']=='clinicaltrials.gov' for t in body['trials'])
    assert len(calls)==2 # canonical search plus one pre-reviewed synonym probe
    assert body['trace'][1]['details']['candidate_count']==1
    assert body['model_calls']==0


def test_model_calls_require_explicit_server_opt_in(monkeypatch):
    monkeypatch.delenv('ENABLE_LIVE_AI',raising=False)
    response=client.post('/api/v1/matching/analyze',json={
        'mode':'replay','depth':'model','profile':patient(), 'max_studies':1})
    assert response.status_code==503


def test_rejects_invalid_or_forged_live_study_ids():
    response=client.post('/api/v1/matching/analyze',json={
        'mode':'live','depth':'tools','profile':patient(),
        'study_ids':['DEMO-001']})
    assert response.status_code==422


def test_clarification_rechecks_all_linked_studies():
    initial=client.post('/api/v1/matching/analyze',json={
        'mode':'replay','depth':'tools','profile':patient()})
    assert initial.status_code==200,initial.text
    before=initial.json()
    reply=client.post('/api/v1/matching/clarify',json={
        'mode':'replay','depth':'tools','profile':before['profile'],
        'study_ids':[t['nct_id'] for t in before['trials']],
        'updates':{'age':{'state':'answered','value':'42'}}})
    assert reply.status_code==200,reply.text
    after=reply.json()
    assert {x['nct_id'] for x in after['changed_criteria']}=={'DEMO-001','DEMO-002','DEMO-003'}
    assert all(x['after']=='met' for x in after['changed_criteria'])
    assert len(after['trace'])==5
    assert after['model_calls']==0


def test_budget_enforces_caps_before_dispatch(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('GEMINI_API_KEY','test-only-key')
    async def fake_generate_json(**_): return {'ok':True}
    monkeypatch.setattr('app.agents.budget.generate_json',fake_generate_json)
    budget=AgentBudget(maximum=2)
    async def run():
        for _ in range(2):
            assert await budget.generate(model='fake',system='fake',payload={})=={'ok':True}
        with pytest.raises(AgentBudgetExceeded):
            await budget.generate(model='fake',system='fake',payload={})
    asyncio.run(run())
    assert budget.calls==2


def test_agent_model_blindness_and_safe_schema_validation(monkeypatch):
    # No live provider calls. Run both analyst and skeptic with identical original
    # sources but not each other's conclusions, and check the origin of citations.
    captured=[]
    async def fake_model(self,*,model,system,payload):
        captured.append((system,payload))
        if 'criteria' in payload:
            return {'assessments':[{'criterion_id':c['id'],'status':'unknown',
                    'explanation':'Not enough patient evidence','patient_evidence':[],
                    'question_for_doctor':'Ask the study team'} for c in payload['criteria']]}
        return {'ordered_fact_keys':[x['fact_key'] for x in payload.get('questions',[])]}
    monkeypatch.setattr(AgentBudget,'generate',fake_model)
    from app.agents.orchestrator import execute
    from app.agents.contracts import AgentRunRequest
    from app.schemas import PatientProfile
    req=AgentRunRequest(profile=PatientProfile.model_validate(patient('sickle cell disease',29)),
                        mode='replay',depth='model',max_studies=1)
    result=asyncio.run(execute(req,model_authorized=True))
    assert len(result.trace)==5
    assert any(t.agent=='analyst' and t.execution=='model' for t in result.trace)
    assert any(t.agent=='skeptic' and t.execution=='model' for t in result.trace)
    assert not any('primary_judgments' in payload or 'first_assessment' in payload for _,payload in captured)
    assert result.assessments[0].summary!='potential_match'


def test_model_capability_detection_requires_backend_configuration(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    monkeypatch.delenv('LIVE_AI_ACCESS_TOKEN',raising=False)
    monkeypatch.delenv('ENABLE_LIVE_AI',raising=False)
    response=client.get('/api/v1/matching/capabilities')
    assert response.status_code==200
    body=response.json()
    assert body['model_ready'] is False
    assert body['model_provider']=='Google Gemini'
    assert 'ENABLE_LIVE_AI' in body['model_readiness_message']

    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    body=client.get('/api/v1/matching/capabilities').json()
    assert body['model_ready'] is False
    assert 'GEMINI_API_KEY' in body['model_readiness_message']

    monkeypatch.setenv('GEMINI_API_KEY','private-test-only-key')
    body=client.get('/api/v1/matching/capabilities').json()
    assert body['model_ready'] is False
    assert 'LIVE_AI_ACCESS_TOKEN' in body['model_readiness_message']

    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','safe-local-testing-access-123')
    body=client.get('/api/v1/matching/capabilities').json()
    assert body['model_ready'] is True
    assert body['analysis_model'] and body['profile_model']
    assert 'private-test-only-key' not in str(body)
    assert 'safe-local-testing-access-123' not in str(body)


def test_model_mode_missing_provider_key_returns_explicit_configuration_error(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','safe-local-testing-access-123')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    response=client.post('/api/v1/matching/analyze',
        headers={'X-Live-Access-Token':'safe-local-testing-access-123'},
        json={'mode':'replay','depth':'model','profile':patient(),'max_studies':1})
    assert response.status_code==503
    assert 'GEMINI_API_KEY' in response.json()['detail']


def test_authorized_model_path_reports_actual_mocked_inference_calls(monkeypatch):
    """Checks API plumbing and accounting; no real provider calls are made."""
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('GEMINI_API_KEY','test-only-never-contact-provider')
    token='local-team-access-token-strong-123'
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN',token)
    async def fake_provider(*,model,system,payload):
        criteria=payload.get('criteria')
        if isinstance(criteria,list):
            return {'assessments':[{'criterion_id':c['id'],'status':'unknown',
                'explanation':'Not enough fictional patient evidence',
                'patient_evidence':[],'question_for_doctor':'Ask the trial team'}
                for c in criteria]}
        if 'questions' in payload:
            return {'ordered_fact_keys':[x['fact_key'] for x in payload['questions']]}
        return {'concerns':[]}
    monkeypatch.setattr('app.agents.budget.generate_json',fake_provider)
    res=client.post('/api/v1/matching/analyze',
        headers={'X-Live-Access-Token':token},
        json={'mode':'replay','depth':'model','profile':patient(),'max_studies':1})
    assert res.status_code==200,res.text
    result=res.json()
    assert result['model_calls']>=2
    trace={x['agent']:x for x in result['trace']}
    assert trace['analyst']['execution']=='model'
    assert trace['skeptic']['execution']=='model'
    assert trace['analyst']['model_calls']>0
    assert trace['skeptic']['model_calls']>0
    assert len(result['assessments'])==1
    assert result['assessments'][0]['provenance']=='live_llm'
