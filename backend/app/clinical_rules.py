"""Narrow parsers for common CF-style requirements beyond age.

Each parser accepts one plainly worded clause. Compound, conditional or
multi-part wording returns None so it stays in clinical review.
"""
import re

N = r'(\d{1,3})'
MODULATORS = (r'(?:cftr modulators?|highly effective modulators?|hem|trikafta|kaftrio|eti|'
              r'elexacaftor(?:/|-| )tezacaftor(?:/|-| )ivacaftor|symdeko|orkambi|kalydeco)')


def _clean(text: str) -> str:
    t = text.lower().replace('≥', '>=').replace('≤', '<=').replace('\\', '')
    return ' '.join(t.split()).rstrip(' .;')


def fev1_bounds(text: str) -> tuple[int | None, int | None] | None:
    """Inclusive FEV1 %-predicted (min, max) from a single threshold or range."""
    t = re.sub(r'forced expiratory volume in (?:1|one) second(?:\s*\(fev\s*1(?:\.0)?\))?', 'fev1', _clean(text))
    t = ' '.join(re.sub(r'\([^)]*\)', ' ', t).split())
    head = r'(?:[a-z ]*?)(?:fev1(?:\.0)?|fev 1)\s*(?:%\s*predicted|percent predicted)?\s*(?:of\s+)?'
    tail = r'\s*(?:%|percent)?\s*(?:of )?(?:predicted)?(?: at [a-z ]+)?'
    if m := re.fullmatch(rf'{head}(?:between|of)?\s*{N}\s*(?:%|percent)?\s*(?:and|to|-)\s*{N}{tail}', t):
        lo, hi = int(m[1]), int(m[2])
        return (lo, hi) if lo <= hi else None
    if m := re.fullmatch(rf'{head}(?:>=|at least|greater than or equal to|no less than)\s*{N}{tail}', t):
        return int(m[1]), None
    if m := re.fullmatch(rf'{head}(?:<=|at most|no more than|less than or equal to)\s*{N}{tail}', t):
        return None, int(m[1])
    if m := re.fullmatch(rf'{head}(?:>|greater than|above|more than)\s*{N}{tail}', t):
        return int(m[1]) + 1, None
    if m := re.fullmatch(rf'{head}(?:<|less than|below|under)\s*{N}{tail}', t):
        return None, int(m[1]) - 1
    return None


def f508del_minimum_copies(text: str) -> int | None:
    """Copies of F508del required: 1 for "at least one copy", 2 for homozygous."""
    t = _clean(text)
    t = re.sub(r'^(?:confirmed )?(?:diagnosis of )?(?:cf|cystic fibrosis)(?: \([^)]*\))? and ', '', t)
    if re.fullmatch(r'(?:at least one|>=\s*1|one or two) cop(?:y|ies) of (?:the )?f508del(?: mutation)?(?: in the cftr gene)?', t):
        return 1
    if re.fullmatch(r'(?:homozygous for (?:the )?f508del(?: mutation)?|two copies of (?:the )?f508del(?: mutation)?)', t):
        return 2
    return None


def modulator_use_clause(text: str) -> bool:
    """True for a bare current-use clause such as "Currently taking Trikafta"."""
    t = _clean(text)
    return bool(re.fullmatch(
        rf'(?:currently |current )?(?:(?:taking|receiving|on|treated with|using|use of|treatment with)\s+)?'
        rf'(?:a |an |any )?(?:stable (?:dose|regimen) of )?{MODULATORS}(?: therapy| treatment)?', t))


def pregnancy_clause(text: str) -> bool:
    t = _clean(text)
    return bool(re.fullmatch(
        r'(?:currently )?(?:pregnan(?:t|cy)|breast[- ]?feeding|lactating|pregnant,? (?:or )?(?:breast[- ]?feeding|lactating|nursing)|'
        r'pregnant (?:or|and/or) (?:breast[- ]?feeding|lactating|nursing)|pregnant or nursing)(?: women| females)?', t))
