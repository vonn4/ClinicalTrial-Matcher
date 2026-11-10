"""Pure-Python BM25: no vector server or expensive dependency needed."""
import math, re
from collections import Counter
from .schemas import TrialRecord, PatientProfile
from .location_relevance import location_priority

def tokenize(text: str) -> list[str]:
    return re.findall(r'[a-z0-9]+', text.lower())

def rank_trials(profile: PatientProfile, studies: list[TrialRecord]) -> list[TrialRecord]:
    if not studies:
        return []
    query=' '.join(filter(None,[profile.diagnosis,profile.stage,' '.join(profile.biomarkers),' '.join(profile.treatments)]))
    qterms=set(tokenize(query))
    docs=[tokenize(' '.join([s.title,' '.join(s.conditions),s.brief_summary[:650],s.eligibility_text[:1300]])) for s in studies]
    avg=sum(map(len,docs))/len(docs) or 1
    df=Counter(word for d in docs for word in set(d))
    N=len(docs)
    for study, tokens in zip(studies,docs):
        tf=Counter(tokens)
        score=0.0
        for term in qterms:
            if term not in tf: continue
            idf=math.log(1+(N-df[term]+0.5)/(df[term]+0.5))
            norm=tf[term]*2.2/(tf[term]+1.2*(.25+.75*len(tokens)/avg))
            score+=idf*norm
        # Recruitment relevance is not used as an eligibility conclusion.
        score += location_priority(profile, study)
        study.relevance_score=round(score,4)
    return sorted(studies,key=lambda s:(-s.relevance_score,s.nct_id))
