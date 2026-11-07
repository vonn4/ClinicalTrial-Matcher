"""Guard against a static dashboard masquerading as a functional interactive demo."""
from fastapi.testclient import TestClient
from app.main import app
from app.replay import sample_profile

client = TestClient(app)


def submit(description):
    parsed = client.post('/api/v1/profiles/parse', json={'mode':'replay','description':description})
    assert parsed.status_code == 200, parsed.text
    analyzed = client.post('/api/v1/analysis/run', json={'mode':'replay','profile':parsed.json()})
    assert analyzed.status_code == 200, analyzed.text
    return analyzed.json()


def test_custom_oncology_profile_is_interactive_but_not_falsely_assessed():
    result = submit('26-year-old patient with stage III non-small cell lung cancer. Previously received chemotherapy.')
    assert result['profile']['age'] == 26
    assert result['trials'] and all(t['source'] == 'synthetic_fixture' for t in result['trials'])
    assert result['assessments'] == []
    assert 'No eligibility' in result['disclaimer']


def test_different_diagnoses_change_results():
    sickle = submit('29-year-old patient with sickle cell disease. Lives in Chicago, Illinois.')
    cf = submit('16-year-old patient with cystic fibrosis. Lives in Chicago, Illinois.')
    assert [t['nct_id'] for t in sickle['trials']] == ['DEMO-004']
    assert [t['nct_id'] for t in cf['trials']] == ['DEMO-005']
    assert sickle['profile']['diagnosis'] != cf['profile']['diagnosis']
    assert not sickle['assessments'] and not cf['assessments']


def test_replay_does_not_trust_client_tampering():
    p = sample_profile().model_dump()
    p['age'] = 18
    r = client.post('/api/v1/analysis/run', json={'mode':'replay','profile':p})
    assert r.status_code == 200
    assert r.json()['profile']['age'] == 42


def test_unknown_diagnosis_is_not_falsely_matched():
    r = submit('26-year-old synthetic patient with a made-up syndrome which has no represented studies.')
    assert r['trials'] == [] and r['assessments'] == []
