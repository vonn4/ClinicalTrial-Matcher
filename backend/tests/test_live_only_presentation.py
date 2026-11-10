"""The public application must never silently return fictional study records."""
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.replay import sample_profile, replay_trials
from app.schemas import (
    Mode, ProfileRequest, SearchRequest, AssessRequest, AnalysisRequest, FollowupRequest
)

def test_public_api_defaults_are_live():
    profile = sample_profile()
    assert ProfileRequest(description=profile.description).mode == Mode.live
    assert SearchRequest(profile=profile).mode == Mode.live
    assert AssessRequest(profile=profile, trial=replay_trials()[0]).mode == Mode.live
    assert AnalysisRequest(profile=profile).mode == Mode.live
    assert FollowupRequest(profile=profile, trial_ids=['NCT12345678']).mode == Mode.live
    assert TestClient(app).get('/health').json()['mode_default'] == 'live'

def test_fictional_fixture_route_stays_internal_for_regression():
    client=TestClient(app)
    assert client.get('/api/v1/demo/cases').status_code == 200
    assert '/api/v1/demo/cases' not in client.get('/openapi.json').json()['paths']

def test_client_has_no_mock_trial_entries_or_prefilled_patient():
    frontend = Path(__file__).resolve().parents[2] / 'frontend' / 'src'
    app_src = (frontend / 'App.tsx').read_text(encoding='utf8')
    guided = (frontend / 'components' / 'GuidedIntake.tsx').read_text(encoding='utf8')
    assert 'SANDBOX_EXAMPLES' not in app_src
    assert 'DEMO-' not in app_src
    assert 'offlineAnalysis' not in app_src
    assert 'Fictional sandbox' not in app_src
    assert 'EXAMPLES.map' not in guided
    assert not (frontend / 'data' / 'fixture.ts').exists()
    assert not (frontend / 'data' / 'replay.json').exists()
    assert 'requireOfficialStudies(result.trials)' in app_src

def test_public_quick_profile_works_without_ai_token_even_when_model_enabled(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_AI', 'true')
    client=TestClient(app)
    response=client.post('/api/v1/profiles/parse',json={
        'mode':'live',
        'description':'Fictional 31-year-old patient with sickle cell disease, prior treatment unknown.'})
    assert response.status_code==200,response.text
    assert response.json()['diagnosis']=='sickle cell disease'


def test_five_agent_workflow_runs_on_search_without_redundant_play_button():
    frontend = Path(__file__).resolve().parents[2] / 'frontend' / 'src'
    app_src = (frontend / 'App.tsx').read_text(encoding='utf8')
    trace_src = (frontend / 'components' / 'AgentWorkflow.tsx').read_text(encoding='utf8')
    setup_src = (frontend / 'components' / 'AgentSetup.tsx').read_text(encoding='utf8')

    assert 'Run five-agent workflow' not in trace_src
    assert 'runFiveAgents(' not in trace_src
    assert '<button' not in trace_src
    assert 'Execution summary' in trace_src
    assert app_src.count('const settings=selectedAgentSettings();') == 2
    assert app_src.count('const result=await runFiveAgents(') == 2
    assert '<AgentSetup depth={analysisDepth}' in app_src
    assert '<AgentWorkflow result={agentResult}/>' in app_src
    assert 'model_ready' in setup_src
    assert 'onDepthChange' in setup_src
    assert 'LIVE_AI_ACCESS_TOKEN' in setup_src
