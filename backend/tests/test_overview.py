from app.followups import build_followup_plan
from app.intake import build_profile
from app.overview import with_overviews
from app.reassessment import review_trial
from app.schemas import IntakeAnswer, IntakeSubmission, TrialRecord

TEXT = ('Inclusion Criteria:\n- Aged 19 years or older\n- FEV1 < 90% predicted\n- Stable clinical status\n'
        'Exclusion Criteria:\n- Pregnant or breastfeeding\n')


def test_overview_counts_and_next_questions():
    profile = build_profile(IntakeSubmission(answers={
        'condition': IntakeAnswer(state='answered', value='cystic fibrosis'),
        'age': IntakeAnswer(state='answered', value='17')}))
    trial = TrialRecord(nct_id='NCT00000001', title='t', conditions=['Cystic Fibrosis'], status='RECRUITING', phase=[],
                        locations=[], eligibility_text=TEXT, brief_summary='', source='clinicaltrials.gov',
                        url='https://clinicaltrials.gov/study/NCT00000001')
    plan = build_followup_plan(profile, [trial])
    [result] = with_overviews([review_trial(profile, trial)], plan)
    o = result.overview
    assert (o.total, o.not_met) == (4, 1) and o.met == 0
    assert o.inclusions_failed == ['Aged 19 years or older']
    assert o.unknown == 2 and o.clinical_review == 1
    assert o.resolved_by_rules == 0  # only model-path assessments carry a source label
    assert any('FEV1' in q for q in o.top_missing_questions) and len(o.top_missing_questions) <= 3
    assert o.exclusions_triggered == []
