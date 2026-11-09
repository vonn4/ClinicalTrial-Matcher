from app.reasoning import dependencies, affected_criteria
from app.schemas import TrialRecord

def test_dependencies_preserve_opaque_clauses():
    t=TrialRecord(nct_id='NCT12345678',title='Test only',source='clinicaltrials.gov',minimum_age='18 Years',
        eligibility_text='Inclusion Criteria:\n- ECOG 0 or 1 and adequate organ function')
    deps=dependencies([t]);keys={x.fact_key for x in deps}
    assert 'age' in keys
    assert None in keys
    assert all(d.source_verified for d in deps)
    assert affected_criteria([t],'age')==[('NCT12345678','REG-AGE')]
    assert not affected_criteria([t],'egfr_result')
