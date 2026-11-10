import asyncio

from app.agents.analyst_agent import execute, split_by_rules
from app.agents.budget import AgentBudget
from app.intake import build_profile
from app.schemas import IntakeAnswer, IntakeSubmission, TrialRecord

TEXT = ('Inclusion Criteria:\n- Aged 19 years or older\n- Confirmed cystic fibrosis diagnosis\n'
        '- Stable clinical status per the treating physician\n')


def _inputs(age):
    profile = build_profile(IntakeSubmission(answers={
        'condition': IntakeAnswer(state='answered', value='cystic fibrosis'),
        'diagnosis_confirmation': IntakeAnswer(state='answered', value='Confirmed'),
        'age': IntakeAnswer(state='answered', value=str(age))}))
    trial = TrialRecord(nct_id='NCT00000001', title='t', conditions=['Cystic Fibrosis'], status='RECRUITING',
                        phase=[], locations=[], eligibility_text=TEXT, brief_summary='', source='clinicaltrials.gov',
                        url='https://clinicaltrials.gov/study/NCT00000001')
    return profile, trial


def test_only_unresolved_criteria_reach_the_model(monkeypatch):
    profile, trial = _inputs(24)
    _, settled, pending = split_by_rules(profile, trial)
    assert {c.source_text for c in pending} == {'Stable clinical status per the treating physician'}
    assert len(settled) == 2
    seen = []

    async def fake(self, *, model, system, payload):
        seen.append([c['source_text'] for c in payload['criteria']])
        return {'assessments': [{'criterion_id': c['id'], 'status': 'unknown', 'explanation': 'x', 'patient_evidence': []}
                                for c in payload['criteria']]}
    monkeypatch.setattr(AgentBudget, 'generate', fake)
    results, meta = asyncio.run(execute(profile, [trial], model=True, budget=AgentBudget(9)))
    assert seen == [['Stable clinical status per the treating physician']]
    by = {a.criterion_id: a for a in results[0].assessments}
    assert [by[c.id].source for c in results[0].criteria] == ['rules', 'rules', 'model']
    assert meta['model_invoked'] and results[0].provenance == 'live_llm'


def test_rule_verdict_beats_contradicting_model(monkeypatch):
    profile, trial = _inputs(17)

    async def fake(self, *, model, system, payload):
        # A model that wrongly claims every criterion is met for a 17-year-old.
        return {'assessments': [{'criterion_id': c['id'], 'status': 'met', 'explanation': 'm',
                                 'patient_evidence': [profile.description[:10]]} for c in payload['criteria']]}
    monkeypatch.setattr(AgentBudget, 'generate', fake)
    results, _ = asyncio.run(execute(profile, [trial], model=True, budget=AgentBudget(9)))
    age = next(a for c, a in zip(results[0].criteria, results[0].assessments) if 'Aged 19' in c.source_text)
    assert age.status == 'not_met' and age.source == 'rules'


def test_fully_rule_resolved_study_makes_no_model_calls(monkeypatch):
    profile, trial = _inputs(24)
    trial = trial.model_copy(update={'eligibility_text': 'Inclusion Criteria:\n- Aged 19 years or older\n'})

    async def boom(self, **_):
        raise AssertionError('model must not be called')
    monkeypatch.setattr(AgentBudget, 'generate', boom)
    budget = AgentBudget(9)
    results, meta = asyncio.run(execute(profile, [trial], model=True, budget=budget))
    assert budget.calls == 0 and not meta['model_invoked']
    assert results[0].assessments[0].status == 'met'
