"""Reject fabricated reference metrics and count missed exclusions explicitly."""
from pathlib import Path
import importlib.util
import pytest
source=Path(__file__).resolve().parents[2]/'evaluation'/'evaluate_agent_ablations.py'
spec=importlib.util.spec_from_file_location('agent_ablation_eval',source)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
LABELS=[
 {'case_id':'1','nct_id':'NCT12345678','criterion_id':'IN-1','kind':'inclusion','gold_status':'met'},
 {'case_id':'1','nct_id':'NCT12345678','criterion_id':'EX-1','kind':'exclusion','gold_status':'met'}
]
def test_metrics_penalize_unsafe_clearance_and_missing_criteria():
    preds=[{'method':'baseline','case_id':'1','nct_id':'NCT12345678','criterion_id':'IN-1','status':'met'},
      {'method':'baseline','case_id':'1','nct_id':'NCT12345678','criterion_id':'EX-1','status':'not_met'},
      {'method':'skeptic','case_id':'1','nct_id':'NCT12345678','criterion_id':'EX-1','status':'met'}]
    m=module.score(LABELS,preds)['methods']
    assert m['baseline']['unsafe_exclusion_clearances']==1
    assert m['baseline']['exclusion_trigger_recall']==0
    assert m['skeptic']['exclusion_trigger_recall']==1
    assert m['skeptic']['submitted_predictions']==1
    assert m['skeptic']['decisive_coverage']==.5
def test_rejects_invented_criteria_and_duplicate_predictions():
    p={'method':'baseline','case_id':'1','nct_id':'NCT12345678','criterion_id':'IN-1','status':'met'}
    with pytest.raises(ValueError):module.score(LABELS,[p,p])
    with pytest.raises(ValueError):module.score(LABELS,[{**p,'criterion_id':'FAKE'}])
