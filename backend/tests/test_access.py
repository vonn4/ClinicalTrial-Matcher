from fastapi.testclient import TestClient
from app.main import app
from app.replay import sample_profile

def test_model_endpoint_rejects_unguarded_live_access():
    c=TestClient(app)
    p=sample_profile()
    res=c.post('/api/v1/analysis/run',json={'mode':'live','profile':p.model_dump()})
    assert res.status_code==503

def test_live_requires_access_token_even_if_flag_enabled(monkeypatch):
    c=TestClient(app)
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','example-long-local-secret-123')
    res=c.post('/api/v1/analysis/run',json={'mode':'live','profile':sample_profile().model_dump()})
    assert res.status_code==403

def test_no_bad_host_or_token_reflection(monkeypatch):
    c=TestClient(app)
    monkeypatch.setenv('ENABLE_LIVE_AI','true')
    monkeypatch.setenv('LIVE_AI_ACCESS_TOKEN','example-long-local-secret-123')
    res=c.post('/api/v1/analysis/run',headers={'X-Live-Access-Token':'wrong'},json={'mode':'live','profile':sample_profile().model_dump()})
    assert res.status_code==403
    assert 'example-long' not in res.text
