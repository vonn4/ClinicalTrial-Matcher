import pytest
from backend.app.clinical_rules import fev1_bounds, f508del_minimum_copies, modulator_use_clause, pregnancy_clause
from backend.app.followups import map_criterion
from backend.app.reassessment import review_criterion
from backend.app.intake import build_profile
from backend.app.schemas import IntakeAnswer, IntakeSubmission, Criterion, TrialRecord


@pytest.mark.parametrize('text,expected', [
    ('FEV1 < 90% predicted', (None, 89)),
    ('Forced Expiratory Volume in 1 second (FEV1.0) \\< 90% predicted', (None, 89)),
    ('FEV1 >= 40% predicted', (40, None)),
    ('FEV1 between 40% and 90% predicted', (40, 90)),
    ('FEV1 of at least 50% of predicted', (50, None)),
])
def test_fev1_thresholds(text, expected):
    assert fev1_bounds(text) == expected


def test_fev1_compound_wording_stays_in_review():
    assert fev1_bounds('FEV1 < 90% predicted or hospitalization in the last 6 months') is None
    assert fev1_bounds('Stable clinical status') is None


def test_f508del_and_modulator_clauses():
    assert f508del_minimum_copies('At least one copy of the F508del mutation in the CFTR gene') == 1
    assert f508del_minimum_copies('Homozygous for F508del') == 2
    assert f508del_minimum_copies('At least one copy of F508del and FEV1 > 40%') is None
    assert modulator_use_clause('Currently taking Trikafta')
    assert not modulator_use_clause('Plan to initiate Trikafta by the treating physician within 30 days')
    assert pregnancy_clause('Pregnant or breastfeeding')
    assert not pregnancy_clause('Pregnant women who have a documented ultrasound')


def _profile(**answers):
    base = {'condition': IntakeAnswer(state='answered', value='cystic fibrosis')}
    base.update({k: IntakeAnswer(state='answered', value=v) for k, v in answers.items()})
    return build_profile(IntakeSubmission(answers=base))


def _trial(text):
    return TrialRecord(nct_id='NCT00000001', title='t', conditions=['Cystic Fibrosis'], status='RECRUITING',
                       phase=[], locations=[], eligibility_text=text, brief_summary='', url='https://clinicaltrials.gov/study/NCT00000001',
                       source='clinicaltrials.gov')


def test_questions_are_mapped_and_unanswered_stays_unknown():
    assert map_criterion('FEV1 < 90% predicted', 'inclusion') == 'fev1_percent'
    assert map_criterion('At least one copy of the F508del mutation', 'inclusion') == 'f508del_copies'
    assert map_criterion('Pregnant or breastfeeding', 'exclusion') == 'pregnant_or_breastfeeding'
    trial = _trial('Inclusion Criteria:\n- FEV1 < 90% predicted')
    c = Criterion(id='IN-1', kind='inclusion', text='FEV1 < 90% predicted', source_text='FEV1 < 90% predicted')
    assert review_criterion(_profile(), trial, c).status == 'unknown'


def test_answered_follow_up_gives_decisions():
    trial = _trial('Inclusion Criteria:\n- FEV1 < 90% predicted\n- At least one copy of the F508del mutation\nExclusion Criteria:\n- Pregnant or breastfeeding')
    inc = [Criterion(id='IN-1', kind='inclusion', text='FEV1 < 90% predicted', source_text='FEV1 < 90% predicted'),
           Criterion(id='IN-2', kind='inclusion', text='At least one copy of the F508del mutation', source_text='At least one copy of the F508del mutation')]
    ex = Criterion(id='EX-1', kind='exclusion', text='Pregnant or breastfeeding', source_text='Pregnant or breastfeeding')
    p = _profile().model_copy(update={'followup_answers': {
        'fev1_percent': IntakeAnswer(state='answered', value='72'),
        'f508del_copies': IntakeAnswer(state='answered', value='None'),
        'pregnant_or_breastfeeding': IntakeAnswer(state='answered', value='No')}})
    assert review_criterion(p, trial, inc[0]).status == 'met'
    assert review_criterion(p, trial, inc[1]).status == 'not_met'
    r = review_criterion(p, trial, ex)
    assert r.status == 'not_met' and r.exclusion_triggered is False
