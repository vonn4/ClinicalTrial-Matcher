import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_retrieval_metrics():
    m=load(ROOT/'evaluation'/'evaluate_retrieval.py','metrics')
    results=m.metrics_for({'NCT00000001':2,'NCT00000002':1,'NCT00000003':0},['NCT00000002','NCT00000001'],10)
    assert 0<results['ndcg@10']<1
    assert results['precision@10']==.2
    assert results['eligible_recall@10']==1

def test_monitor_diff():
    m=load(ROOT/'scripts'/'monitor_studies.py','monitor')
    changes=m.diff({'NCT00000001':{'updated':'2026-01-01','recruitment_status':'RECRUITING'}},
                   {'NCT00000001':{'updated':'2026-02-01','recruitment_status':'COMPLETED'}})
    assert len(changes)==1
    assert 'recruitment_status' in changes[0]['changed_fields']
