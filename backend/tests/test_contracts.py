from fastapi.testclient import TestClient
from app.main import app
from app.replay import sample_profile,replay_trials,replay_assessments
from app.criteria import extract_criteria
from app.profiling import deterministic_profile
from app.ranking import rank_trials

client=TestClient(app)

def test_health_and_demo():
    h=client.get('/health');assert h.status_code==200 and h.json()['synthetic_only']
    sample=client.get('/api/v1/demo/cases');assert sample.status_code==200
    assert sample.json()['profile']['diagnosis']=='non-small cell lung cancer'

def test_profile_no_hallucinated_egfr_status():
    profile=sample_profile()
    assert profile.age==42 and profile.stage.lower()=='stage iii'
    assert 'EGFR' in profile.biomarkers
    assert not any(f.field=='mutation_positive' for f in profile.facts)

def test_replay_analysis_and_criteria_coverage():
    profile=sample_profile()
    res=client.post('/api/v1/analysis/run',json={'profile':profile.model_dump(),'mode':'replay','limit':3})
    assert res.status_code==200,res.text
    output=res.json();assert output['mode']=='replay'
    assert len(output['trials'])==3
    assert len(output['assessments'])==3
    for a in output['assessments']:
        assert len(a['criteria'])==len(a['assessments'])==len(a['skeptic'])
        assert a['provenance']=='synthetic_replay'
    conflict=next(a for a in output['assessments'] if a['nct_id']=='DEMO-002')
    assert conflict['summary']=='identified_conflict'
    assert any(x['exclusion_triggered'] for x in conflict['assessments'])

def test_replay_refuses_modified_patient():
    profile=sample_profile().model_copy(update={'description':'45-year-old person with breast cancer.'})
    res=client.post('/api/v1/analysis/run',json={'mode':'replay','profile':profile.model_dump()})
    assert res.status_code==400

def test_live_ai_default_disabled():
    profile=sample_profile()
    res=client.post('/api/v1/analysis/run',json={'mode':'live','profile':profile.model_dump()})
    assert res.status_code==503

def test_criteria_inventory_and_exact_quote():
    trials=replay_trials()
    for trial in trials:
        criteria=extract_criteria(trial.eligibility_text)
        assert criteria
        assert all(c.source_text in trial.eligibility_text for c in criteria)

def test_ranking_relevance_not_eligibility():
    trials=rank_trials(sample_profile(),replay_trials())
    assert len(trials)==3 and all(t.relevance_score>=0 for t in trials)
    assert all(t.source=='synthetic_fixture' for t in trials)

def test_no_measured_results_fabricated():
    result=client.get('/api/v1/evaluation/summary').json()
    assert result['status']=='not_measured' and not result['experiments']
