"""Minimal research-demo guard for free-tier AI quota. Not production authentication."""
import os,secrets,time
from collections import deque
from fastapi import HTTPException,Request
from .settings import enabled
CALLS=deque()

def require_live_ai(request:Request):
    if not enabled('ENABLE_LIVE_AI'):
        raise HTTPException(503,'Live AI disabled. Use replay mode or enable on a trusted local backend.')
    configured=os.getenv('LIVE_AI_ACCESS_TOKEN','')
    if len(configured)<16:
        raise HTTPException(503,'Live AI needs a strong server-side LIVE_AI_ACCESS_TOKEN before use.')
    supplied=request.headers.get('X-Live-Access-Token','')
    if not secrets.compare_digest(configured,supplied):
        raise HTTPException(403,'Live AI requires the team access token')
    now=time.monotonic()
    while CALLS and CALLS[0]<now-3600:CALLS.popleft()
    max_per_hour=min(max(int(os.getenv('MAX_LIVE_AI_REQUESTS_PER_HOUR','12')),1),30)
    if len(CALLS)>=max_per_hour:
        raise HTTPException(429,'Local demo model-call cap reached; no automatic upgrade is possible')
    CALLS.append(now)
