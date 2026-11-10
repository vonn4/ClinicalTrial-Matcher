"""Regression: active provider, not Gemini, controls model-mode availability."""
from app.agents.api import capabilities, model_readiness

def test_openai_ready_without_gemini_key(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OPENAI_API_KEY','test-local-key')
    monkeypatch.setenv('OPENAI_ALLOW_BILLABLE','true')
    monkeypatch.setenv('OPENAI_MODEL','gpt-4.1-mini')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','test-team-token-long-enough')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    ready, message=model_readiness()
    assert ready is True
    assert 'Openai' in message
    data=capabilities()
    assert data['model_ready'] is True
    assert data['model_provider']=='OpenAI'
    assert data['analysis_model']=='gpt-4.1-mini'

def test_openai_requires_explicit_billing_consent(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OPENAI_API_KEY','test-local-key')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','test-team-token-long-enough')
    monkeypatch.delenv('OPENAI_ALLOW_BILLABLE',raising=False)
    assert model_readiness()[0] is False
    assert 'OPENAI_ALLOW_BILLABLE' in model_readiness()[1]

def test_gemini_still_works_without_openai(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','gemini')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('GEMINI_API_KEY','test-local-key')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','test-team-token-long-enough')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert model_readiness()[0] is True
    assert capabilities()['model_provider']=='Google Gemini'
