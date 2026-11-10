import pytest
from backend.app.age_rules import age_bounds
from backend.app.criteria import extract_criteria


@pytest.mark.parametrize('text,expected', [
    ('Aged 19 years or older', (19, None)),
    ('Adults 18 years of age or older', (18, None)),
    ('Age 18-65 years', (18, 65)),
    ('Between 6 and 17 years of age', (6, 17)),
    ('Less than 10 years of age at the first study visit.', (None, 9)),
    ('At least 18 years old', (18, None)),
    ('Age >= 12 years', (12, None)),
])
def test_plain_age_clauses(text, expected):
    assert age_bounds(text) == expected


@pytest.mark.parametrize('text', [
    'Participated in Part A OR less than 7 years of age at the first study visit.',
    "Age 6 years and up (if age is \< 12 years old, the caregiver will consent)",
    'Body mass index greater than 16 or less than 30 kg/m\^2',
    'Infants younger than 6 months',
    'Stable clinical status',
])
def test_compound_or_conditional_wording_is_left_for_review(text):
    assert age_bounds(text) is None


def test_label_only_lines_are_not_criteria():
    found = extract_criteria('Inclusion Criteria:\nPart A:\n- Aged 19 years or older\nExclusion Criteria:\n- Pregnancy')
    assert [c.text for c in found] == ['Aged 19 years or older', 'Pregnancy']
