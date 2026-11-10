"""Mocked OpenAI adapter tests. Never contact or bill a real API."""
import asyncio
import json
import httpx
import pytest
from app.llm import generate_json, ModelUnavailable
from app.agents.budget import AgentBudget, _calls


def test_openai_json_success_and_safe_request(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OPENAI_ALLOW_BILLABLE','true')
    monkeypatch.setenv('OPENAI_API_KEY','mock-key-for-tests')
    monkeypatch.setenv('OPENAI_MODEL','gpt-4.1-mini')
    captured=[]
    original=httpx.AsyncClient
    def handler(req):
        captured.append(req)
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'assessments':[]})}}]})
    monkeypatch.setattr('app.llm.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    result=asyncio.run(generate_json(model='unused-gemini-model',system='Only JSON',payload={'role':'primary_analyst'}))
    assert result=={'assessments':[]}
    assert str(captured[0].url)=='https://api.openai.com/v1/chat/completions'
    assert json.loads(captured[0].content)['model']=='gpt-4.1-mini'
    assert captured[0].headers['Authorization']=='Bearer mock-key-for-tests'


def test_no_billable_calls_without_explicit_consent(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OPENAI_API_KEY','mock-key-for-tests')
    monkeypatch.delenv('OPENAI_ALLOW_BILLABLE',raising=False)
    _calls.clear()
    budget=AgentBudget()
    with pytest.raises(ModelUnavailable,match='OPENAI_ALLOW_BILLABLE'):
        asyncio.run(budget.generate(model='x',system='x',payload={}))
    assert budget.calls==0


def test_openai_http_429_not_retried(monkeypatch):
    monkeypatch.setenv('AI_PROVIDER','openai')
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('OPENAI_API_KEY','mock-key-for-tests')
    monkeypatch.setenv('OPENAI_ALLOW_BILLABLE','true')
    _calls.clear()
    called=[]
    original=httpx.AsyncClient
    def handler(req):
        called.append(req)
        return httpx.Response(429,json={'error':{'message':'quota exceeded'}})
    monkeypatch.setattr('app.llm.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(AgentBudget().generate(model='x',system='x',payload={}))
    assert len(called)==1
