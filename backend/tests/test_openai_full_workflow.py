"""Provider-specific five-agent integration with mocked OpenAI HTTP responses only."""
from __future__ import annotations
import json
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.agents.budget import _calls


def test_openai_analyst_and_independent_skeptic_complete_without_gemini(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'openai')
    monkeypatch.setenv('OPENAI_MODEL', 'gpt-4.1-mini')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-only-private-placeholder-key')
    monkeypatch.setenv('OPENAI_ALLOW_BILLABLE', 'true')
    monkeypatch.setenv('ENABLE_LIVE_AI', 'true')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN', 'local-test-team-token-123456')
    monkeypatch.setenv('MAX_AGENT_MODEL_CALLS_PER_HOUR', '60')
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    _calls.clear()
    original = httpx.AsyncClient
    observed_roles = []
    def respond(request):
        assert request.url.host == 'api.openai.com'
        data=json.loads(request.content)
        assert data['model'] == 'gpt-4.1-mini'
        assert data['response_format'] == {'type':'json_object'}
        payload=json.loads(data['messages'][1]['content'])
        role=payload.get('role')
        if role in {'primary_analyst','independent_skeptic'}:
            observed_roles.append(role)
            answer={'assessments':[
                {'criterion_id': c['id'], 'status':'unknown','exclusion_triggered':None,
                 'explanation':'Not enough confirmed fictional patient facts.',
                 'patient_evidence':[], 'question_for_doctor':None}
                for c in payload['criteria']
            ]}
        elif 'questions' in payload:
            answer={'ordered_fact_keys':[q['fact_key'] for q in payload['questions']]}
        else:
            answer={'concerns':[]}
        return httpx.Response(200, json={'choices':[{'message':{'content':json.dumps(answer)}}]})
    monkeypatch.setattr('app.llm.httpx.AsyncClient',lambda **kw:
                        original(transport=httpx.MockTransport(respond),**kw))
    client=TestClient(app)
    profile=client.post('/api/v1/intake/profile',json={
        'answers':{'condition':{'state':'answered','value':'non-small cell lung cancer'},
                   'age':{'state':'answered','value':'42'}},
        'narrative':'Entirely fictional patient record for API integration testing.',
        'synthetic':True
    }).json()
    response=client.post('/api/v1/matching/analyze',
        headers={'X-Live-Access-Token':'local-test-team-token-123456'},
        json={'mode':'replay','depth':'model','profile':profile,
              'max_studies':1,'study_ids':['DEMO-001']})
    assert response.status_code==200,response.text
    result=response.json()
    trace={stage['agent']:stage for stage in result['trace']}
    assert trace['analyst']['execution']=='model'
    assert trace['skeptic']['execution']=='model'
    assert trace['analyst']['model_calls']>=1
    assert trace['skeptic']['model_calls']>=1
    assert 'primary_analyst' in observed_roles
    assert 'independent_skeptic' in observed_roles
    assert result['model_calls']<=9
    assert result['assessments'][0]['skeptic']
