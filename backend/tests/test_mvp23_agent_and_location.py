"""Regression checks for structured Gemini output, 30-line protocols and travel ranking.

Every provider and registry call is mocked. No patient data, secrets or paid APIs.
"""
import asyncio
import json
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.agents.budget import AgentBudget
from app.agents import discovery_agent
from app.schemas import TrialRecord, PatientProfile
from app.ranking import rank_trials

client = TestClient(app)
TOKEN = 'fixture-team-token-long-and-safe'


def make_trial(nct, location, count=2):
    text = 'Inclusion Criteria:\n' + '\n'.join(
        '- Criterion ' + str(i) + ': documented research condition required'
        for i in range(1, count + 1))
    return TrialRecord(nct_id=nct, title='Fictional cystic fibrosis study',
                       conditions=['Cystic Fibrosis'], status='RECRUITING',
                       locations=[location], eligibility_text=text,
                       source='clinicaltrials.gov')


def make_profile(narrative=''):
    response = client.post('/api/v1/intake/profile', json={
        'synthetic': True,
        'answers': {
            'condition': {'state':'answered','value':'Cystic fibrosis'},
            'age': {'state':'answered','value':'27'},
            'location': {'state':'answered','value':'Seattle, Washington'},
            'travel': {'state':'answered','value':'Within 250 miles'},
            'cftr_result': {'state':'unknown','value':None},
        },
        'narrative': narrative,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_city_state_ranking_is_preference_not_fake_radius():
    profile = PatientProfile.model_validate(make_profile())
    distant = make_trial('NCT12345678', 'Los Angeles, California, United States')
    nearby = make_trial('NCT23456789', 'Seattle, Washington, United States')
    same_state = make_trial('NCT34567890', 'Tacoma, Washington, United States')
    ranked = rank_trials(profile, [distant, same_state, nearby])
    assert [x.nct_id for x in ranked] == ['NCT23456789', 'NCT34567890', 'NCT12345678']
    assert nearby.location_fit == 'preferred_city'
    assert same_state.location_fit == 'preferred_state'
    assert distant.location_fit == 'other_location'
    assert all('distance' in x.location_explanation.lower() for x in ranked)
    assert all('250' not in x.location_explanation for x in ranked)


def test_schema_is_sent_only_for_judgment_requests(monkeypatch):
    from app import llm
    monkeypatch.setenv('ENABLE_LIVE_AI', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'local-mock-key-not-a-real-secret')
    captured = []
    def fake_reply(request):
        body = json.loads(request.content)
        captured.append(body)
        return httpx.Response(200, json={'candidates':[{'content':{'parts':[{'text':'{"assessments": []}'}]}}]})
    original = httpx.AsyncClient
    def mocked_client(*_args, **_kwargs):
        return original(transport=httpx.MockTransport(fake_reply))
    monkeypatch.setattr(llm.httpx, 'AsyncClient', mocked_client)
    async def run():
        return await llm.generate_json(model='gemini-3.5-flash', system='safe', payload={
            'role':'primary_analyst','criteria':[]})
    assert asyncio.run(run()) == {'assessments': []}
    assert captured[0]['generationConfig']['responseMimeType'] == 'application/json'
    assert 'responseJsonSchema' in captured[0]['generationConfig']
    assert captured[0]['generationConfig']['responseJsonSchema']['properties']['assessments']


def test_long_study_gets_all_criteria_and_independent_skeptic(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI', 'true')
    monkeypatch.setenv('GEMINI_API_KEY', 'not-a-real-key')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN', TOKEN)
    monkeypatch.setenv('MAX_AGENT_MODEL_CALLS_PER_HOUR', '24')
    large = make_trial('NCT12345678', 'Seattle, Washington, United States', 30)
    extra = make_trial('NCT23456789', 'Los Angeles, California, United States', 30)
    async def search(_query, limit=80):
        return [large.model_copy(deep=True), extra.model_copy(deep=True)]
    monkeypatch.setattr(discovery_agent, 'search_trials', search)
    # A Seattle, 250-mile guided profile now uses official radius discovery.
    async def near_search(condition, lat, lon, miles, limit=80):
        assert miles == 250
        return await search(condition, limit=limit)
    monkeypatch.setattr(discovery_agent, 'search_trials_geo', near_search)

    calls = []
    async def fake_model(self, *, model, system, payload):
        from app.agents.budget import AgentBudgetExceeded
        if self.calls >= self.maximum:
            raise AgentBudgetExceeded('mock per-run budget exhausted')
        self.calls += 1  # mimic the real budget adapter for truthful call accounting
        calls.append(payload)
        if 'allowed_terms' in payload:
            return {'terms': []}
        if 'criteria' in payload:
            assert len(payload['criteria']) <= 12
            return {'assessments': [
                {'criterion_id': c['id'], 'status':'unknown',
                 'explanation':'No source-grounded information.',
                 'patient_evidence': [], 'exclusion_triggered': None,
                 'question_for_doctor': None}
                for c in payload['criteria']]}
        if 'questions' in payload:
            return {'ordered_fact_keys':[q['fact_key'] for q in payload['questions']]}
        return {'concerns': []}
    monkeypatch.setattr(AgentBudget, 'generate', fake_model)
    result = client.post('/api/v1/matching/analyze',
        headers={'X-Live-Access-Token':TOKEN},
        json={'mode':'live','depth':'model','profile':make_profile(),'max_studies':2})
    assert result.status_code == 200, result.text
    data = result.json()
    assert 7 <= data['model_calls'] <= 9
    assert len(data['assessments'][0]['criteria']) == 30
    assert len(data['assessments'][0]['assessments']) == 30
    assert data['assessments'][0]['provenance'] == 'live_llm'
    assert len(data['assessments'][0]['skeptic']) == 30
    assert data['trace'][2]['details']['model_reviewed'] >= 1
    assert data['trace'][3]['details']['independent_trials'] >= 1
    assert data['trace'][2]['details']['budget_skips'] == 1
    assert data['assessments'][1]['provenance'] == 'deterministic_followup'
    assert 'used rules-only review to preserve independent Skeptic' in data['notice']
    assert all(a['status'] == 'unknown' for a in data['assessments'][0]['assessments'])
    primary = [p for p in calls if p.get('role') == 'primary_analyst']
    skeptic = [p for p in calls if p.get('role') == 'independent_skeptic']
    assert len(primary) >= 3 and len(skeptic) >= 3
    assert all('primary_judgments' not in payload for payload in skeptic)


def test_unsupported_extra_long_protocol_falls_back_without_claiming_ai(monkeypatch):
    from app.agents.analyst_agent import execute
    profile = PatientProfile.model_validate(make_profile())
    too_long = make_trial('NCT12345678', 'Seattle, Washington', 45)
    async def never_call(*_a,**_kw):
        raise AssertionError('This study must not use Gemini')
    budget = AgentBudget(maximum=9)
    monkeypatch.setattr(budget, 'generate', never_call)
    reviews, meta = asyncio.run(execute(profile, [too_long], model=True, budget=budget))
    assert meta['criteria_limit_skips'] == 1
    assert meta['model_reviewed'] == 0
    assert len(reviews[0].criteria) >= 45
    assert reviews[0].provenance == 'deterministic_followup'


def test_skeptic_unavailable_preserves_preexisting_exclusion_or_inclusion_conflict():
    """A missing independent review must not hide an already flagged safety conflict."""
    from app.agents.skeptic_agent import execute
    from app.criteria import extract_criteria
    from app.schemas import CriterionAssessment, TrialAssessment

    profile = PatientProfile.model_validate(make_profile())
    study = make_trial('NCT12345678', 'Seattle, Washington, United States')
    criteria = extract_criteria(study.eligibility_text)
    primary = TrialAssessment(
        nct_id=study.nct_id,
        criteria=criteria,
        assessments=[
            CriterionAssessment(
                criterion_id=c.id,
                status='not_met' if i == 0 else 'unknown',
                patient_evidence=['age: 27.'] if i == 0 else [],
                verified_evidence=True,
            ) for i, c in enumerate(criteria)
        ],
        skeptic=[],
        summary='identified_conflict',
        provenance='live_llm',
    )
    reconciled, meta = asyncio.run(
        execute(profile, [study], [primary], model=False, budget=AgentBudget())
    )
    assert meta['model_invoked'] is False
    assert reconciled[0].summary == 'identified_conflict'
    assert reconciled[0].skeptic == []
    assert any('Independent AI skeptic review not completed' in msg
               for msg in reconciled[0].unresolved)
