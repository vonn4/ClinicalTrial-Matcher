"""Condition-level evidence for explaining ClinicalTrials.gov search results.

The official query.cond endpoint can retrieve conceptually related records through
indexing. A result becomes a *displayed disease match* only when its original
study record explicitly lists/mentions the entered condition or a small,
source-vetted synonym. This is NOT medical eligibility.
"""
from __future__ import annotations
import re
from .schemas import TrialRecord

# Curated synonyms only. Abetalipoproteinemia aliases: NIH MedlinePlus Genetics
# https://medlineplus.gov/genetics/condition/abetalipoproteinemia/
# Other aliases below reflect common literal acronyms; do not infer new diagnoses.
SYNONYM_GROUPS = (
    ('abetalipoproteinemia', 'abetalipoproteinaemia', 'bassen-kornzweig syndrome', 'bassen-kornzweig disease'),
    ('non-small cell lung cancer', 'nsclc', 'non small cell lung carcinoma'),
    ('sickle cell disease', 'sickle cell anemia', 'sickle cell anaemia'),
    ('glioblastoma', 'glioblastoma multiforme'),
)
WORD = re.compile(r'[a-z0-9]+')

def normalize(value: str) -> str:
    return ' '.join(WORD.findall(value.casefold()))

def documented_terms(condition: str) -> tuple[str, ...]:
    exact = normalize(condition)
    for group in SYNONYM_GROUPS:
        normalized = tuple(normalize(term) for term in group)
        if exact in normalized:
            return tuple(dict.fromkeys((exact, *normalized)))
    return (exact,)

def phrase_in(text: str, term: str) -> bool:
    # Token boundaries keep 'ms' from matching 'asthma' and avoid loose fragments.
    normalized = normalize(text)
    return bool(normalized and re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', normalized))

def explain_condition_match(condition: str, study: TrialRecord) -> TrialRecord | None:
    """Annotate explicit source links; reject records returned only by broad indexing.

    Both exact name and vetted aliases can be registry-listed. A bare mention in
    narrative is weaker, even when it appears in eligibility language.
    """
    if study.source != 'clinicaltrials.gov':
        return study
    query = normalize(condition)
    if not query:
        return None
    terms = documented_terms(query)
    for listed in study.conditions:
        if normalize(listed) == query:
            return study.model_copy(update={
                'match_type': 'listed_condition',
                'match_explanation': f'Listed study condition: {listed}',
                'broad_registry': ('registry' in study.title.casefold() or len(study.conditions)>10)
            })
    for listed in study.conditions:
        if normalize(listed) in terms:
            return study.model_copy(update={
                'match_type':'documented_synonym',
                'match_explanation': f'Listed as {listed}, a documented synonym of {condition}.',
                'broad_registry': ('registry' in study.title.casefold() or len(study.conditions)>10)
            })
    for field_name,text in (('title',study.title), ('summary',study.brief_summary),
                             ('eligibility criteria',study.eligibility_text)):
        if any(phrase_in(text,term) for term in terms):
            return study.model_copy(update={
                'match_type':'text_mention',
                'match_explanation': f'The study {field_name} mentions {condition} or a documented synonym; trial relevance and eligibility need review.',
                'broad_registry': ('registry' in study.title.casefold() or len(study.conditions)>10)
            })
    # ClinicalTrials.gov may return records via MeSH/related-term indexing;
    # never present these as a direct disease match without study-level text.
    return None

def filter_condition_matches(condition: str, studies: list[TrialRecord]) -> list[TrialRecord]:
    matched = []
    for study in studies:
        result = explain_condition_match(condition, study)
        if result is not None:
            matched.append(result)
    return matched
