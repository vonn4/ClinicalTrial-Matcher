"""Optional Gemini embedding reranking; disabled by default and never required for MVP1."""
from __future__ import annotations
import math,os
import httpx
from .schemas import PatientProfile,TrialRecord
from .ranking import rank_trials

async def embed(text:str)->list[float]:
    if os.getenv('ENABLE_SEMANTIC','').lower() not in {'1','true','yes'}:
        raise RuntimeError('Semantic embedding is disabled')
    key=os.getenv('GEMINI_API_KEY','')
    if not key:raise RuntimeError('Missing free-tier Gemini API key')
    model=os.getenv('GEMINI_EMBEDDING_MODEL','gemini-embedding-001')
    if model!='gemini-embedding-001':raise RuntimeError('Unapproved embedding model')
    url=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent'
    payload={'model':f'models/{model}', 'content':{'parts':[{'text':text[:4500]}]}}
    async with httpx.AsyncClient(timeout=35,follow_redirects=False) as client:
        result=await client.post(url,headers={'x-goog-api-key':key},json=payload)
        result.raise_for_status()
    values=result.json()['embedding']['values']
    if not values or not all(isinstance(x,(int,float)) for x in values):
        raise RuntimeError('Invalid embedding response')
    return values

def cosine(a:list[float],b:list[float])->float:
    if len(a)!=len(b) or not a:return 0.0
    dot=sum(x*y for x,y in zip(a,b)); denom=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b))
    return dot/denom if denom else 0.0

async def semantic_rerank(profile:PatientProfile,studies:list[TrialRecord],limit:int=10)->list[TrialRecord]:
    """Rerank a bounded pool; does not recover studies absent from first-stage retrieval.

    Not assumed better than BM25; require historical TREC validation before claiming gains.
    """
    if not studies:return []
    first=rank_trials(profile,studies)[:min(20,len(studies))]
    query=' '.join(filter(None,[profile.diagnosis,profile.stage,' '.join(profile.treatments),' '.join(profile.biomarkers)]))
    query_vec=await embed(query)
    sims=[]
    for t in first:
        t_vec=await embed(' '.join([t.title,' '.join(t.conditions),t.brief_summary[:500]]))
        sims.append((t,cosine(query_vec,t_vec)))
    sims.sort(key=lambda tup:-tup[1])
    return [t for t,_ in sims[:limit]]
