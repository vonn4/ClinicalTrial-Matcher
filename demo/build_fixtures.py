"""Generate explicit synthetic and clearly labeled REPLAY demonstrations (never clinical ground truth)."""
from pathlib import Path
import json
ROOT=Path(__file__).parent
DESCRIPTION='42-year-old patient with stage III non-small cell lung cancer. Previously received chemotherapy. Lives in Kansas City, Missouri. EGFR mutation status is unknown.'
TRIALS=[
 dict(nct_id='DEMO-001',title='Synthetic trial: targeted therapy after prior chemotherapy',
      conditions=['Non-Small Cell Lung Cancer'],status='RECRUITING',phase=['PHASE2'],
      locations=['Kansas City, Missouri, United States'],
      eligibility_text='Inclusion Criteria:\n- Patient is at least 18 years old\n- Histologically confirmed non-small cell lung cancer\n- Known EGFR activating mutation\nExclusion Criteria:\n- Active uncontrolled infection',
      brief_summary='Synthetic oncology study for demonstration only.',updated='2026-11-05',
      url=None,source='synthetic_fixture',retrieved_at=None,relevance_score=4.21),
 dict(nct_id='DEMO-002',title='Synthetic trial: first-line therapy for untreated NSCLC',
      conditions=['Non-Small Cell Lung Cancer'],status='NOT_YET_RECRUITING',phase=['PHASE3'],
      locations=['St. Louis, Missouri, United States'],
      eligibility_text='Inclusion Criteria:\n- Adult patient at least 18 years old\n- Non-small cell lung cancer diagnosis\nExclusion Criteria:\n- Any prior systemic chemotherapy',
      brief_summary='Synthetic first-line oncology study for demonstration only.',updated='2026-11-04',
      url=None,source='synthetic_fixture',retrieved_at=None,relevance_score=3.88),
 dict(nct_id='DEMO-003',title='Synthetic trial: investigational immunotherapy in advanced NSCLC',
      conditions=['Non-Small Cell Lung Cancer'],status='RECRUITING',phase=['PHASE1'],
      locations=['Chicago, Illinois, United States'],
      eligibility_text='Inclusion Criteria:\n- Adults 18 years or older\n- Stage III or IV non-small cell lung cancer\nExclusion Criteria:\n- Active autoimmune disease requiring immunosuppressive medications',
      brief_summary='Synthetic oncology study with additional medical screening required.',updated='2026-10-29',
      url=None,source='synthetic_fixture',retrieved_at=None,relevance_score=3.51),
]
# Explicit replay records, not fabricated model outputs. All statuses conservative.
DATA=[
 {'status':['met','met','unknown','unknown'], 'ev':['42-year-old','non-small cell lung cancer',None,None], 'skeptic':['met','met','unknown','unknown'], 'summary':'needs_information'},
 {'status':['met','met','met'], 'ev':['42-year-old','non-small cell lung cancer','chemotherapy'], 'skeptic':['met','met','met'], 'summary':'identified_conflict'},
 {'status':['met','met','unknown'], 'ev':['42-year-old','stage III non-small cell lung cancer',None], 'skeptic':['met','met','unknown'], 'summary':'needs_information'}]
# The independent agent's missed-exclusion detection is shown in a separate *illustrative* scenario
# within the evaluation explanation, not fabricated as a measured result.
from sys import path
path.insert(0,str(ROOT.parent/'backend'))
from app.criteria import extract_criteria

assessments=[]
for trial,data in zip(TRIALS,DATA):
    crit=extract_criteria(trial['eligibility_text'])
    results=[];skeptic=[]
    for criterion,status,ev,skeptic_status in zip(crit,data['status'],data['ev'],data['skeptic']):
        triggered=status=='met' if criterion.kind=='exclusion' and status in ('met','not_met') else None
        results.append({'criterion_id':criterion.id,'status':status,'exclusion_triggered':triggered,
            'explanation': ('Explicit synthetic profile evidence matches this criterion.' if ev else 'Patient profile does not provide enough verified information to decide.'),
            'patient_evidence':[ev] if ev else [],'question_for_doctor':('Can my care team confirm this eligibility requirement?' if not ev else None),
            'verified_evidence':True})
        skeptic.append({'criterion_id':criterion.id,'independent_status':skeptic_status,
            'exclusion_triggered':triggered,'explanation':'Independent replay illustration; not an experimental measurement.',
            'disagreement':False})
    assessments.append({'nct_id':trial['nct_id'],'criteria':[c.model_dump() for c in crit],
        'assessments':results,'skeptic':skeptic,'summary':data['summary'],
        'unresolved':[c.id for c,a in zip(crit,results) if a['status']=='unknown'],
        'provenance':'synthetic_replay'})
fixture={'case_id':'synthetic-nsclc-01','name':'Synthetic NSCLC patient — 42 years old',
    'description':DESCRIPTION,'trials':TRIALS,'assessments':assessments,
    'notice':'Every study and assessment in this replay is synthetic and illustrative; no real clinical trials or model performance claims.'}
(ROOT/'replay_case.json').write_text(json.dumps(fixture,indent=2)+'\n')
(ROOT.parent/'backend'/'app'/'data'/'replay_case.json').write_text(json.dumps(fixture,indent=2)+'\n')
(ROOT.parent/'frontend'/'src'/'data'/'replay.json').write_text(json.dumps(fixture,indent=2)+'\n')
print('Wrote demo/replay_case.json')
