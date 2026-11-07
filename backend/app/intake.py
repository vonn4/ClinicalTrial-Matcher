"""MVP 1.5-A: deterministic, synthetic-only guided intake.

The server owns the question vocabulary and builds canonical facts from explicit
answers. A pending test is NEVER a negative test, and unknown is NEVER no.
No trial-specific eligibility inference occurs in this module.
"""
from __future__ import annotations
from .schemas import IntakeQuestion, IntakeSubmission, IntakeAnswer, PatientProfile, Fact
from .profiling import deterministic_profile

QUESTIONS: list[IntakeQuestion] = [
    IntakeQuestion(id='condition', label='Which condition are you exploring trials for?',
                   help='Enter a diagnosed or suspected condition. This determines which follow-up questions are relevant.',
                   section='basics', input_type='text', required_for_search=True,
                   placeholder='e.g., non-small cell lung cancer'),
    IntakeQuestion(id='diagnosis_confirmation', label='Has a clinician confirmed the diagnosis?',
                   help='Do not assume a condition is confirmed just because it was entered.',
                   section='basics', input_type='select', options=['Confirmed', 'Suspected', 'Unsure']),
    IntakeQuestion(id='age', label='What is the patient\'s age in years?',
                   help='An approximate age can help identify age-restricted studies.',
                   section='basics', input_type='number', placeholder='e.g., 42'),
    IntakeQuestion(id='subtype', label='Is a disease subtype or more specific diagnosis known?',
                   help='Use the terminology in the fictional diagnosis or leave it unknown.',
                   section='basics', input_type='text', placeholder='e.g., adenocarcinoma'),
    IntakeQuestion(id='stage', label='What is the cancer stage?',
                   help='Cancer stage only; for other conditions this question is not shown.',
                   section='basics', input_type='select', options=['Stage 0', 'Stage I', 'Stage II', 'Stage III', 'Stage IV'],
                   conditions=['non-small cell lung cancer', 'lung cancer', 'breast cancer', 'glioblastoma']),
    IntakeQuestion(id='previous_treatments', label='Which treatments have been received previously?',
                   help='Mention treatment names if known. Never assume no treatment from an empty field.',
                   section='history', input_type='text', placeholder='e.g., chemotherapy'),
    IntakeQuestion(id='current_treatments', label='What treatments are being received currently?',
                   help='Current and previous treatments must be distinguished.',
                   section='history', input_type='text', placeholder='e.g., immunotherapy'),
    IntakeQuestion(id='egfr_result', label='What is the EGFR tumor test result?',
                   help='A named test is not a positive result. Record positive, negative, pending, or not tested explicitly.',
                   section='history', input_type='select', options=['Positive / detected', 'Negative / not detected', 'Inconclusive'],
                   conditions=['non-small cell lung cancer', 'lung cancer']),
    IntakeQuestion(id='alk_result', label='What is the ALK tumor test result?',
                   help='Unknown, pending and negative results have different meanings.',
                   section='history', input_type='select', options=['Positive / detected', 'Negative / not detected', 'Inconclusive'],
                   conditions=['non-small cell lung cancer', 'lung cancer']),
    IntakeQuestion(id='sickle_genotype', label='Is the sickle cell genotype known?',
                   help='Use a documented genotype; do not guess.',
                   section='history', input_type='select', options=['HbSS', 'HbSC', 'HbS-beta-thalassemia', 'Other confirmed genotype'],
                   conditions=['sickle cell disease']),
    IntakeQuestion(id='cftr_result', label='What is known about CFTR genetic testing?',
                   help='A known result and a test awaiting results are not interchangeable.',
                   section='history', input_type='text', placeholder='e.g., F508del detected',
                   conditions=['cystic fibrosis']),
    IntakeQuestion(id='her2_result', label='What is the HER2 testing result?',
                   help='Record only a known result, otherwise choose an uncertainty status.',
                   section='history', input_type='select', options=['Positive', 'Negative', 'Equivocal'],
                   conditions=['breast cancer']),
    IntakeQuestion(id='location', label='Where should we prioritize trial locations?',
                   help='City and state are sufficient for the synthetic research demo. Avoid street addresses.',
                   section='access', input_type='text', placeholder='e.g., Kansas City, Missouri'),
    IntakeQuestion(id='travel', label='How far could the patient travel for a study?',
                   help='This expresses a preference, not a medical eligibility requirement.',
                   section='access', input_type='select', options=['Local only', 'Within 50 miles', 'Within 100 miles', 'Within 250 miles', 'Flexible / anywhere']),
]
QUESTION_BY_ID = {q.id: q for q in QUESTIONS}
TEST_RESULT_KEYS = {'egfr_result', 'alk_result', 'cftr_result', 'her2_result', 'sickle_genotype'}

# Treat aliases in a dedicated normalization layer, not as medical diagnoses inferred by AI.
ALIASES = {'nsclc': 'non-small cell lung cancer', 'sickle cell anemia': 'sickle cell disease'}


def normalize_condition(text: str) -> str:
    value = ' '.join(text.lower().strip().split())
    return ALIASES.get(value, value)


def question_bank(condition: str | None = None) -> list[IntakeQuestion]:
    diagnosis = normalize_condition(condition or '')
    return [q for q in QUESTIONS if not q.conditions or diagnosis in q.conditions]


def build_profile(submission: IntakeSubmission) -> PatientProfile:
    answers = submission.answers
    for key, answer in answers.items():
        question = QUESTION_BY_ID.get(key)
        if question is None:
            raise ValueError(f'Unrecognized intake question: {key}')
        if answer.state in {'pending', 'not_tested'} and key not in TEST_RESULT_KEYS:
            raise ValueError(f'State {answer.state} does not apply to {key}')
        if answer.state == 'answered' and question.options and answer.value not in question.options:
            raise ValueError(f'Invalid choice for {key}')
    condition_answer = answers.get('condition')
    if not condition_answer or condition_answer.state != 'answered':
        raise ValueError('Enter a condition before building the patient profile')
    diagnosis = normalize_condition(condition_answer.value or '')
    if len(diagnosis) < 3 or len(diagnosis) > 120:
        raise ValueError('Condition must be between 3 and 120 characters')
    permitted = {q.id for q in question_bank(diagnosis)}
    invalid = set(answers) - permitted
    if invalid:
        raise ValueError(f'Questions not relevant for the selected condition: {", ".join(sorted(invalid))}')

    age_answer = answers.get('age')
    age: int | None = None
    if age_answer and age_answer.state == 'answered':
        raw = age_answer.value or ''
        if not raw.isascii() or not raw.isdigit():
            raise ValueError('Age must be a whole number')
        age = int(raw)
        if age > 120:
            raise ValueError('Age must be between 0 and 120')

    fact_rows: list[Fact] = []
    for question in question_bank(diagnosis):
        answer = answers.get(question.id)
        if answer and answer.state == 'answered':
            value = diagnosis if question.id == 'condition' else answer.value or ''
            if len(value) > 250:
                raise ValueError(f'Answer for {question.id} is too long (250 character maximum)')
            fact_rows.append(Fact(field=question.id, value=value,
                                  evidence=f'{question.label} — {value}', source='guided_answer'))

    # Free-text is retained as a patient-provided story, not silently promoted into
    # verified structured facts. This prevents a contradictory story from replacing
    # answers the user explicitly reviewed. A later review stage can suggest edits.
    lines = ['Synthetic guided patient profile.']
    for f in fact_rows:
        lines.append(f'{f.field}: {f.value}.')
    if submission.narrative.strip():
        lines.append('Unverified patient story: ' + submission.narrative.strip())
    description = ' '.join(lines)
    if len(description) > 3000:
        raise ValueError('Combined profile description is too long')

    def known(key: str) -> str | None:
        a = answers.get(key)
        return a.value if a and a.state == 'answered' else None

    treatment_values = [known('previous_treatments'), known('current_treatments')]
    treatments = [v for v in treatment_values if v]
    biomarker_ids = {'egfr_result': 'EGFR', 'alk_result': 'ALK', 'cftr_result': 'CFTR', 'her2_result': 'HER2'}
    biomarkers = [f'{marker}: {known(key)}' for key, marker in biomarker_ids.items() if known(key)]
    relevant = [q for q in question_bank(diagnosis) if q.id not in {'condition', 'travel'}]
    unknowns = [f'{q.id}: {answers[q.id].state}' if q.id in answers else f'{q.id}: unanswered'
                for q in relevant if q.id not in answers or answers[q.id].state != 'answered']

    return PatientProfile(description=description, age=age, diagnosis=diagnosis,
                          stage=known('stage'), biomarkers=biomarkers, treatments=treatments,
                          location=known('location'), facts=fact_rows, unknowns=unknowns,
                          intake_answers=answers, intake_story=submission.narrative)


def profile_from_guided_or_text(profile: PatientProfile) -> PatientProfile:
    """Rebuild trusted fields instead of accepting a client-modified canonical profile."""
    if profile.intake_answers:
        # Narrative is NOT round-tripped separately. The original guided description
        # is informational; the canonical structure derives from explicit answers.
        return build_profile(IntakeSubmission(answers=profile.intake_answers, narrative=profile.intake_story))
    return deterministic_profile(profile.description)
