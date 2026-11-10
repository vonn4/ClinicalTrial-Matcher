import asyncio

from app.agents import analyst_agent, skeptic_agent
from app.agents.budget import AgentBudget
from app.intake import build_profile
from app.schemas import IntakeAnswer, IntakeSubmission, TrialRecord

A = lambda v: IntakeAnswer(state='answered', value=v)


def _trial(nct, text):
    return TrialRecord(nct_id=nct, title='t', conditions=['Cystic Fibrosis'], status='RECRUITING', phase=[], locations=[],
                       eligibility_text=text, brief_summary='', source='clinicaltrials.gov',
                       url=f'https://clinicaltrials.gov/study/{nct}')


def _profile():
    return build_profile(IntakeSubmission(answers={'condition': A('cystic fibrosis'), 'age': A('24')}))


def test_every_study_is_labelled_with_how_it_was_really_reviewed(monkeypatch):
    # Budget of 4 covers exactly one study (2 analyst + 2 skeptic chunks of its 13..24 criteria); the rest cannot be model-reviewed.
    many = 'Inclusion Criteria:\n' + '\n'.join(f'- Stable clinical status number {i}' for i in range(18))
    small = 'Inclusion Criteria:\n- Stable clinical status A\n- Stable clinical status B'
    huge = 'Inclusion Criteria:\n' + '\n'.join(f'- Requirement {i}' for i in range(40))
    trials = [_trial('NCT00000001', small), _trial('NCT00000002', many), _trial('NCT00000003', huge)]

    async def fake(self, *, model, system, payload):
        return {'assessments': [{'criterion_id': c['id'], 'status': 'unknown', 'explanation': 'x', 'patient_evidence': []}
                                for c in payload['criteria']]}
    monkeypatch.setattr(AgentBudget, 'generate', fake)
    profile = _profile()
    budget = AgentBudget(maximum=4)
    primary, _ = asyncio.run(analyst_agent.execute(profile, trials, model=True, budget=budget))
    by = {a.nct_id: a for a in primary}
    assert by['NCT00000001'].review_basis == 'model_analyst_only'
    assert by['NCT00000002'].review_basis == 'rules_only' and 'budget' in by['NCT00000002'].rules_only_reason
    assert by['NCT00000003'].review_basis == 'rules_only' and 'Too many criteria' in by['NCT00000003'].rules_only_reason
    reviewed, _ = asyncio.run(skeptic_agent.execute(profile, trials, primary, model=True, budget=AgentBudget(maximum=9)))
    assert {a.nct_id: a.review_basis for a in reviewed} == {
        'NCT00000001': 'model_and_skeptic', 'NCT00000002': 'rules_only', 'NCT00000003': 'rules_only'}


def test_tools_mode_is_labelled_rules_only():
    results, meta = asyncio.run(analyst_agent.execute(_profile(), [_trial('NCT00000001', 'Inclusion Criteria:\n- Aged 19 years or older')],
                                                      model=False, budget=AgentBudget()))
    assert results[0].review_basis == 'rules_only' and 'not selected' in results[0].rules_only_reason
    assert not meta['model_invoked']
