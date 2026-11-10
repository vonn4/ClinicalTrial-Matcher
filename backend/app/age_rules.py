"""Inclusive (min, max) age bounds from one plainly worded free-text age clause.

Deliberately narrow: months/days, conditional wording ("if age < 12") and compound
clauses return None so they stay in clinical review rather than being guessed.
"""
import re

N = r'(\d{1,3})'
Y = r'(?:years?|yrs?)'
OLDER = r'(?:or|and) (?:older|above|over)\+?'


def age_bounds(text: str) -> tuple[int | None, int | None] | None:
    t = ' '.join(text.lower().replace(chr(0x2265), '>=').replace(chr(0x2264), '<=').replace(chr(92), '').split()).rstrip(' .;')
    if re.search(r'\b(?:months?|days?|weeks?|if|unless|except|caregiver|parent|guardian)\b', t):
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
