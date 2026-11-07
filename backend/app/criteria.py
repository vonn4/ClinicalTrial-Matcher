"""Conservative inventory of line-oriented CT.gov criteria; don't split compound clauses."""
import re
from .schemas import Criterion

def extract_criteria(text: str) -> list[Criterion]:
    criteria=[];kind='inclusion'
    for raw in text.splitlines():
        line=raw.strip()
        if not line:continue
        if re.match(r'^(key\s+)?inclusion\s+criteria\s*:?$',line,re.I):
            kind='inclusion';continue
        if re.match(r'^(key\s+)?exclusion\s+criteria\s*:?$',line,re.I):
            kind='exclusion';continue
        match=re.match(r'^(inclusion|exclusion)\s+criteria\s*:\s*(.+)$',line,re.I)
        if match:
            kind=match.group(1).lower();line=match.group(2)
        line=re.sub(r'^(?:[-*•]\s*|\d+[.)]\s*)','',line).strip()
        if not line or line.lower() in {'inclusion','exclusion','criteria'}:continue
        n=1+sum(c.kind==kind for c in criteria)
        criteria.append(Criterion(id=f'{"IN" if kind=="inclusion" else "EX"}-{n}',kind=kind,
                                  text=line,source_text=line))
    # If the study's unstructured text cannot be safely enumerated, it is never auto-approved.
    return criteria

def validate_evidence(criterion: Criterion,full_source: str) -> bool:
    return bool(criterion.source_text and criterion.source_text in full_source)
