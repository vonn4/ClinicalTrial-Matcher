"""Increment 1.5-B: source-grounded question planning and deduplication."""
from fastapi.testclient import TestClient
from app.main import app
from app.followups import build_followup_plan
from app.schemas import IntakeSubmission, TrialRecord
from app.intake import build_profile

client=TestClient(app)


def ans(value=None,state='answered'):
    return {'state':state, 'value':value if state=='answered' else None}


def profile(answers):
    return client.post('/api/v1/intake/profile',json={'answers':answers, 'synthetic':True}).json()


def plan(p,ids=('DEMO-001','DEMO-002','DEMO-003'),mode='replay'):
    return client.post('/api/v1/intake/followups',json={'profile':p,'mode':mode,'trial_ids':list(ids)})


def test_one_age_question_maps_to_three_distinct_trials():
    p=profile({'condition':ans('non-small cell lung cancer'),'age':ans(state='unknown')})
    r=plan(p)
    assert r.status_code==200,r.text
    data=r.json()
    age=[x for x in data['questions'] if x['fact_key']=='age']
    assert len(age)==1
    assert age[0]['trial_count']==3
    assert {x['nct_id'] for x in age[0]['linked_criteria']}=={'DEMO-001','DEMO-002','DEMO-003'}
    assert age[0]['answer_state']=='unknown'
    assert data['mapped_criterion_count']==10
    assert not data['unmapped_criteria']


def test_each_question_link_exactly_quotes_server_owned_trial():
    p=profile({'condition':ans('non-small cell lung cancer')})
    data=plan(p).json()
    from app.sandbox import all_sandbox_trials
    sources={x.nct_id:x.eligibility_text for x in all_sandbox_trials()}
    for q in data['questions']:
        for ref in q['linked_criteria']:
            assert ref['source_text'] in sources[ref['nct_id']]
            assert ref['criterion_id'].startswith('IN-' if ref['kind']=='inclusion' else 'EX-')


def test_existing_age_and_stage_not_asked_again():
    p=profile({'condition':ans('non-small cell lung cancer'),'age':ans('42'),'stage':ans('Stage III')})
    keys={x['fact_key'] for x in plan(p).json()['questions']}
    assert 'age' not in keys and 'stage' not in keys
    assert 'active_uncontrolled_infection' in keys


def test_pending_not_treated_as_negative_or_answered():
    p=profile({'condition':ans('non-small cell lung cancer'),'egfr_result':ans(state='pending')})
    q=next(x for x in plan(p).json()['questions'] if x['fact_key']=='egfr_result')
    assert q['answer_state']=='pending'
    p=profile({'condition':ans('non-small cell lung cancer'),'egfr_result':ans(state='not_tested')})
    q=next(x for x in plan(p).json()['questions'] if x['fact_key']=='egfr_result')
    assert q['answer_state']=='not_tested'
    p=profile({'condition':ans('non-small cell lung cancer'),'egfr_result':ans('Negative / not detected')})
    assert 'egfr_result' not in {x['fact_key'] for x in plan(p).json()['questions']}


def test_positive_biomarker_needs_variant_specific_followup():
    p=profile({'condition':ans('non-small cell lung cancer'),'egfr_result':ans('Positive / detected')})
    q=next(x for x in plan(p).json()['questions'] if x['fact_key']=='egfr_variant')
    assert q['trial_count']==1
    assert q['linked_criteria'][0]['source_text']=='Known EGFR activating mutation'


def test_prior_chemo_evidence_is_not_asked_again_but_no_other_treatment_is_assumed():
    p=profile({'condition':ans('non-small cell lung cancer'),'previous_treatments':ans('chemotherapy')})
    assert 'prior_systemic_chemotherapy' not in {x['fact_key'] for x in plan(p).json()['questions']}
    p=profile({'condition':ans('non-small cell lung cancer'),'previous_treatments':ans('surgery')})
    assert 'prior_systemic_chemotherapy' in {x['fact_key'] for x in plan(p).json()['questions']}


def test_disease_specific_sandbox_studies():
    p=profile({'condition':ans('sickle cell disease'),'age':ans('29')})
    r=plan(p,['DEMO-004'])
    assert r.status_code==200,r.text
    keys={q['fact_key'] for q in r.json()['questions']}
    assert keys=={'diagnosis_confirmation','prior_stem_cell_transplant'}
    p=profile({'condition':ans('cystic fibrosis')})
    keys={q['fact_key'] for q in plan(p,['DEMO-005']).json()['questions']}
    assert 'cftr_result' in keys and 'recent_lung_transplant' in keys


def test_rejects_spoofed_or_cross_mode_studies():
    p=profile({'condition':ans('non-small cell lung cancer')})
    for ids,mode,expected in [(['DEMO-999'],'replay',404),(['DEMO-001'],'live',422),
                               (['NCT12345678'],'replay',422),(['DEMO-001']*2,'replay',422),
                               (['../../../etc/passwd'],'replay',422)]:
        assert plan(p,ids,mode).status_code==expected,(ids,mode)


def test_unsupported_source_criterion_is_reported_not_invented():
    p=build_profile(IntakeSubmission(answers={'condition':ans('sickle cell disease')}))
    a=TrialRecord(nct_id='DEMO-007',title='Synthetic other',source='synthetic_fixture',
        eligibility_text='Inclusion Criteria:\n- Participants must meet a specialist-determined complex condition')
    result=build_followup_plan(p,[a])
    assert not result.questions
    assert result.mapped_criterion_count==0
    assert len(result.unmapped_criteria)==1


def test_one_age_fact_can_support_different_thresholds_without_creating_a_verdict():
    p=build_profile(IntakeSubmission(answers={'condition':ans('sickle cell disease')}))
    studies=[TrialRecord(nct_id=f'DEMO-00{i}',title='Synthetic',source='synthetic_fixture',
              eligibility_text=f'Inclusion Criteria:\n- Age {age} years or older') for i,age in [(7,18),(8,65)]]
    result=build_followup_plan(p,studies)
    assert len(result.questions)==1
    assert result.questions[0].trial_count==2
    assert 'eligibility' not in result.model_dump().keys()


def test_tampered_client_profile_does_not_change_canonical_guided_facts():
    p=profile({'condition':ans('non-small cell lung cancer'),'age':ans('42')})
    p['age']=None
    assert 'age' not in {x['fact_key'] for x in plan(p).json()['questions']}
