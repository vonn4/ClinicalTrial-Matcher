"""Regression tests for rare-disease term relevance and safe model error reporting."""
from __future__ import annotations
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import TrialRecord
from app.condition_relevance import explain_condition_match, filter_condition_matches
from app.agents import discovery_agent
from app.agents.budget import AgentBudget
from app.agents.model_errors import explain_model_error

client = TestClient(app)
REGISTRY = 'NCT02435940'

def record(nct: str, title: str, conditions: list[str], summary: str='') -> TrialRecord:
    return TrialRecord(
        nct_id=nct,title=title,conditions=conditions,source='clinicaltrials.gov',
        status='RECRUITING',eligibility_text='Inclusion Criteria:\n- Adults with a clinician-confirmed diagnosis',
        brief_summary=summary,phase=[],locations=[]
    )

def profile(condition: str) -> dict:
    r = client.post('/api/v1/intake/profile',json={
        'answers':{'condition':{'state':'answered','value':condition},
                   'age':{'state':'answered','value':'22'}},'synthetic':True})
    assert r.status_code==200,r.text
    return r.json()

def test_abetalipoproteinemia_has_a_source_confirmed_synonym_in_broad_registry():
    study=record(REGISTRY,'Inherited Retinal Degenerative Disease Registry',
        ['Retinal Dystrophy','Bassen-Kornzweig Syndrome','Usher Syndrome']+
        ['Rare Retinal Disease ' + str(i) for i in range(12)])
    result=explain_condition_match('abetalipoproteinemia',study)
    assert result is not None
    assert result.match_type=='documented_synonym'
    assert 'Bassen-Kornzweig Syndrome' in result.match_explanation
    assert result.broad_registry is True
    assert study.match_type is None  # original source model is untouched

def test_search_terms_in_unrelated_indexing_do_not_silently_count_as_disease_matches():
    unrelated=record('NCT12345678','Retinal Disease Cohort',['Retinal Disease'],
        'An observational database of patients with retinal conditions.')
    direct=record('NCT23456789','Abetalipoproteinemia Study',['Abetalipoproteinemia'])
    explicit=record('NCT34567890','Rare Genetics Cohort',['Unclassified Metabolic Disease'],
        'Study enrolls participants with abetalipoproteinemia.')
    matches=filter_condition_matches('abetalipoproteinemia',[unrelated,direct,explicit])
    assert [x.nct_id for x in matches]==['NCT23456789','NCT34567890']
    assert matches[0].match_type=='listed_condition'
    assert matches[1].match_type=='text_mention'

def test_false_shared_words_do_not_allow_retrieval_of_unrelated_studies():
    drug=record('NCT12345678','Sickle Cell Trait Testing',['Sickle Cell Trait'])
    assert explain_condition_match('sickle cell disease',drug) is None
    no_substrings=record('NCT12345679','Disease Registry',['Multiple Sclerosis'])
    assert explain_condition_match('ms',no_substrings) is None

def test_discovery_filters_unrelated_live_hits_and_marks_source_types(monkeypatch):
    direct=record('NCT12345678','Abetalipoproteinemia Therapeutic Study',['Abetalipoproteinemia'])
    unrelated=record('NCT23456789','Retinal Registry',['Retinal Dystrophy'])
    synonym=record(REGISTRY,'Inherited Retinal Degenerative Disease Registry',
        ['Bassen-Kornzweig Syndrome','Retinal Disease','Choroideremia'])
    async def fake_search(condition,limit=80):
        assert condition=='abetalipoproteinemia'
        return [unrelated,synonym,direct]
    monkeypatch.setattr(discovery_agent,'search_trials',fake_search)
    response=client.post('/api/v1/matching/analyze',json={
        'mode':'live','depth':'tools','max_studies':3,'profile':profile('abetalipoproteinemia')})
    assert response.status_code==200,response.text
    result=response.json()
    assert [x['nct_id'] for x in result['trials']]==['NCT12345678',REGISTRY]
    assert result['trials'][1]['match_type']=='documented_synonym'
    assert result['trace'][1]['details']['filtered_unrelated']==1
    assert result['trace'][1]['details']['matched_count']==2
    assert result['candidate_count']==3

def test_all_unrelated_hits_produce_no_fabricated_disease_results(monkeypatch):
    async def fake_search(condition,limit=80):
        return [record('NCT12345678','General Retinal Registry',['Retinal Disease'])]
    monkeypatch.setattr(discovery_agent,'search_trials',fake_search)
    response=client.post('/api/v1/matching/analyze',json={
        'mode':'live','depth':'tools','profile':profile('abetalipoproteinemia')})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['trials']==[]
    assert data['trace'][1]['details']['filtered_unrelated']==1
    assert data['model_calls']==0

def test_safe_provider_categories_do_not_echo_private_error_content():
    req=httpx.Request('POST','https://generativelanguage.googleapis.com/v1beta/models/fake:generateContent')
    for status,wanted in [(401,'authentication'),(403,'access_denied'),(404,'model_unavailable'),(429,'quota_exceeded')]:
        response=httpx.Response(status,request=req)
        exc=httpx.HTTPStatusError('DO NOT PRINT SECRET CONTENT',request=req,response=response)
        data=explain_model_error(exc)
        assert data['model_error']==wanted
        assert data['model_http_status']==status
        assert 'SECRET' not in str(data)

def test_ai_failure_trace_explains_model_access_without_claiming_inference(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('GEMINI_API_KEY','private-test-only-key')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','secure-local-team-token-123456')
    async def fake_search(condition,limit=80):
        return [record('NCT12345678','Abetalipoproteinemia Study',['Abetalipoproteinemia'],
                       'A trial studying abetalipoproteinemia.')]
    monkeypatch.setattr(discovery_agent,'search_trials',fake_search)
    async def fail_call(self,*,model,system,payload):
        req=httpx.Request('POST','https://generativelanguage.googleapis.com/')
        response=httpx.Response(404,request=req)
        raise httpx.HTTPStatusError('Secret should not leak',request=req,response=response)
    monkeypatch.setattr(AgentBudget,'generate',fail_call)
    response=client.post('/api/v1/matching/analyze',
        headers={'X-Live-Access-Token':'secure-local-team-token-123456'},
        json={'mode':'live','depth':'model','max_studies':1,'profile':profile('abetalipoproteinemia')})
    assert response.status_code==200,response.text
    result=response.json()
    assert result['trials'][0]['nct_id']=='NCT12345678'
    assert result['trace'][2]['execution']=='tools'
    assert result['trace'][2]['details']['model_error']=='model_unavailable'
    assert result['trace'][2]['details']['model_http_status']==404
    assert result['trace'][3]['details']['independent_trials']==0
    assert 'Secret should not leak' not in response.text
