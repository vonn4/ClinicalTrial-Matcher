from app.clinicaltrials import parse_study
from app.schemas import TrialRecord
from pydantic import ValidationError
import pytest

def test_protocol_normalization():
    study={'protocolSection':{
        'identificationModule':{'nctId':'NCT12345678','briefTitle':'Example study'},
        'statusModule':{'overallStatus':'RECRUITING','studyLastUpdatePostDateStruct':{'date':'2026-11-01'}},
        'conditionsModule':{'conditions':['Cancer']},
        'designModule':{'phases':['PHASE2']},
        'eligibilityModule':{'eligibilityCriteria':'Inclusion Criteria:\\n- 18 years or older'},
        'contactsLocationsModule':{'locations':[{'city':'Kansas City','state':'Missouri','country':'United States'}]},
        'descriptionModule':{'briefSummary':'Example'},}}
    record=parse_study(study)
    assert record.nct_id=='NCT12345678'
    assert record.url=='https://clinicaltrials.gov/study/NCT12345678'
    assert record.updated=='2026-11-01'
    assert record.source=='clinicaltrials.gov'

@pytest.mark.parametrize('identifier',['NCTbad','http://example.org','DEMO-1000'])
def test_invalid_ids(identifier):
    with pytest.raises(ValidationError):
        TrialRecord(nct_id=identifier,title='Bad',source='synthetic_fixture')
