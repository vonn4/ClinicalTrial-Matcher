"""Inclusive (min, max) age bounds from one plainly worded free-text age clause.

Deliberately narrow: months/days, conditional wording ("if age < 12") and compound
clauses return None so they stay in clinical review rather than being guessed.
"""
import re

# Only these words may surround an age bound. Anything else ("quit smoking for at
# least 2 years", "families of patients under 18", "male patients over 18") is about
# something other than this patient's age alone and must stay in clinical review.
ALLOWED = {'age', 'aged', 'ages', 'adult', 'adults', 'adolescent', 'adolescents', 'patient', 'patients',
           'participant', 'participants', 'subject', 'subjects', 'be', 'are', 'is', 'must', 'at', 'least',
           'year', 'years', 'yr', 'yrs', 'old', 'older', 'above', 'over', 'and', 'or', 'to', 'through', 'between',
           'of', 'less', 'than', 'greater', 'equal', 'more', 'under', 'below', 'younger', 'up', 'no', 'not',
           'most', 'the', 'beginning', 'study', 'a', 'an', 'y', 'o', 'first', 'visit', 'enrollment'}
AGE_WORDS = {'age', 'aged', 'ages', 'old', 'older', 'adult', 'adults', 'adolescent', 'adolescents'}
N = r'(\d{1,3})'
Y = r'(?:years?|yrs?)'
OLDER = r'(?:or|and) (?:older|above|over)\+?'


def age_bounds(text: str) -> tuple[int | None, int | None] | None:
    t = ' '.join(text.lower().replace(chr(0x2265), '>=').replace(chr(0x2264), '<=').replace(chr(92), '').split()).rstrip(' .;')
    if re.search(r'\b(?:months?|days?|weeks?|if|unless|except|caregiver|parent|guardian)\b', t):
        return None
    words = set(re.findall(r'[a-z]+', t))
    if not words <= ALLOWED or not (words & AGE_WORDS or re.search(r'[<>=]', t)):
        return None
    leftover = re.sub(rf'{N}\s*(?:{Y}\s*)?(?:and|to|through)\s*{N}|{OLDER}', '', t)
    if re.search(r'\b(?:or|and)\b', leftover):
        return None
    if m := re.fullmatch(rf'(?:[a-z ]*?)(?:aged?\s*)?(?:between\s+)?{N}\s*(?:{Y})?\s*(?:and|to|through|-)\s*{N}\s*{Y}(?: of age| old)?', t):
        lo, hi = int(m[1]), int(m[2])
        return (lo, hi) if lo <= hi else None
    if m := re.fullmatch(rf'(?:[a-z ]*?)(?:aged?\s*)?{N}\s*{Y}(?: of age| old)?\s*{OLDER}', t):
        return int(m[1]), None
    if m := re.fullmatch(rf'(?:[a-z ]*?)(?:aged?|age)\s*(?:>=|at least|greater than or equal to)\s*{N}(?:\s*{Y})?', t) or \
         re.fullmatch(rf'(?:[a-z ]*?)(?:at least|>=)\s*{N}\s*{Y}(?: of age| old)?', t):
        return int(m[1]), None
    if m := re.fullmatch(rf'(?:[a-z ]*?)(?:aged?|age)?\s*(?:<=|no more than|at most|up to|not older than)\s*{N}\s*(?:{Y})?(?: of age| old)?', t):
        return None, int(m[1])
    if m := re.fullmatch(rf'(?:[a-z ]*?)(?:aged?|age)?\s*(?:<|less than|younger than|under|below)\s*{N}\s*{Y}(?: of age| old)?(?: at [a-z ]+)?', t):
        return None, int(m[1]) - 1
    if m := re.fullmatch(rf'(?:[a-z ]*?)(?:aged?|age)?\s*(?:>|greater than|older than|over)\s*{N}\s*{Y}(?: of age| old)?', t):
        return int(m[1]) + 1, None
    return None
