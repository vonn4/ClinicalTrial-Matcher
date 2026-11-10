"""No-network tests for research data exports and synthetic security probe fixtures."""
from __future__ import annotations
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]

def load(name,path):
    spec=spec_from_file_location(name, ROOT/path)
    module=module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_real_run_summarizer_uses_supplied_measurements(tmp_path):
    module=load('local_latency_summary','evaluation/summarize_local_runs.py')
    stage_names=['profile','discovery','analyst','skeptic','clarification']
    def write(name,multiplier):
        path=tmp_path/name
        path.write_text(json.dumps({
            'schema':'clinicaltrial-matcher-metrics-v1','model_calls':2,
            'stages':[{'agent':s,'duration_ms':(i+1)*1000*multiplier}
                      for i,s in enumerate(stage_names)]
        }),encoding='utf8')
        return path
    report=module.summarize([write('one.json',1),write('two.json',2)])
    assert report['run_count']==2
    assert report['total_seconds']['median']==22.5
    assert report['per_stage']['analyst']['median_seconds']==4.5
    assert report['model_attempts_total']==4
    assert 'Descriptive' in report['caveat']
    with pytest.raises(ValueError):
        module.summarize([])

def test_latency_summarizer_rejects_untrusted_result_shape(tmp_path):
    module=load('local_latency_summary2','evaluation/summarize_local_runs.py')
    p=tmp_path/'bad.json'
    p.write_text('{"schema":"fake","stages":[]}',encoding='utf8')
    with pytest.raises(ValueError):
        module.summarize([p])

def test_prompt_injection_fixture_uses_identical_criterion_inventory():
    module=load('local_synthetic_security_probe','evaluation/security_tests/run_local_probes.py')
    _,_,clean=module.build_case(False)
    _,_,attack=module.build_case(True)
    assert [c.id for c in clean]==[c.id for c in attack]
    assert [c.kind for c in clean]==[c.kind for c in attack]
    assert 'INJECTION_SUCCEEDED' in module.ATTACK
    assert all(c.source_text for c in attack)
