"""Research-only demo backend: replay public-safe, live model gated by server setting."""
import os
import time
import logging
import httpx
import asyncio
from fastapi import FastAPI,HTTPException,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .schemas import (Mode, ProfileRequest,PatientProfile,SearchRequest,SearchResponse,
    AssessRequest,TrialRecord,TrialAssessment,AnalysisRequest,AnalysisResponse,IntakeSubmission,FollowupRequest,FollowupPlan,ReassessmentRequest,ReassessmentResponse)
from .profiling import deterministic_profile,llm_profile
from .ranking import rank_trials
from .clinicaltrials import search_trials,fetch_trial,fetch_trials_by_ids,registry_status,validate_condition
from .assessment import assess_live
from .replay import fixture,sample_profile,replay_trials,replay_assessments
from .sandbox import sandbox_search,is_original_sample,all_sandbox_trials
from .intake import build_profile, question_bank, profile_from_guided_or_text, QUESTIONS
from .followups import build_followup_plan
from .reassessment import reassess
from .llm import ModelUnavailable
from .settings import MAX_TRIALS,enabled
from .access import require_live_ai

logger=logging.getLogger(__name__)
app=FastAPI(title='ClinicalTrial Matcher API',version='0.1.0',
    description='Synthetic-patient research navigation prototype; not clinical advice.')
allowed=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',')
app.add_middleware(CORSMiddleware,allow_origins=[o.strip() for o in allowed if o.strip()],
                   allow_methods=['GET','POST'],allow_headers=['Content-Type','X-Live-Access-Token'])

@app.exception_handler(ModelUnavailable)
async def model_unavailable(_req:Request,exc:ModelUnavailable):
    return JSONResponse(status_code=503,content={'detail':str(exc)})

@app.get('/health')
def health():
    return {'status':'ok','version':'0.1.0','live_ai_enabled':enabled('ENABLE_LIVE_AI'),
            'mode_default':'live','synthetic_only':True}


@app.get('/api/v1/registry/status')
async def official_registry_status():
    """Actively test free official registry connectivity and data freshness."""
    try:
        return await registry_status()
    except (httpx.HTTPError,ValueError) as exc:
        logger.warning('ClinicalTrials.gov status unavailable: %s',type(exc).__name__)
        raise HTTPException(503,'ClinicalTrials.gov is unreachable right now. Live study search requires internet access.') from exc

@app.get('/api/v1/demo/cases', include_in_schema=False)  # legacy internal regression fixture only
def demo_cases():
    f=fixture()
    return {'cases':[{'id':f['case_id'],'name':f['name'],'description':f['description']}],
            'profile':sample_profile().model_dump(),'notice':f['notice']}

@app.get('/api/v1/intake/questions')
def intake_questions(condition: str = '', include_all: bool = False):
    """Public synthetic questionnaire; no AI key or paid API required."""
    return {'version': '1.5-A', 'questions': [q.model_dump() for q in (QUESTIONS if include_all else question_bank(condition))],
            'synthetic_only': True}

@app.post('/api/v1/intake/profile',response_model=PatientProfile)
def intake_profile(submission: IntakeSubmission):
    try:
        return build_profile(submission)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@app.post('/api/v1/intake/followups',response_model=FollowupPlan)
async def intake_followups(req: FollowupRequest):
    """Map original trial requirements to ONE shared question per missing fact.

    Only trial IDs are accepted from the caller. Criteria and source text are
    fetched from server-owned fixtures or the official registry, not supplied
    by the browser. This does not perform eligibility assessment.
    """
    profile=profile_from_guided_or_text(req.profile)
    if req.mode==Mode.replay:
        if any(not trial_id.startswith('DEMO-') for trial_id in req.trial_ids):
            raise HTTPException(422,'Sandbox follow-ups require synthetic DEMO study IDs')
        known={trial.nct_id:trial for trial in all_sandbox_trials()}
        missing=set(req.trial_ids)-set(known)
        if missing:
            raise HTTPException(404,'Synthetic study not found')
        studies=[known[trial_id] for trial_id in req.trial_ids]
    else:
        if any(not trial_id.startswith('NCT') for trial_id in req.trial_ids):
            raise HTTPException(422,'Live follow-ups require official NCT study IDs')
        try:
            studies=await fetch_trials_by_ids(req.trial_ids)
        except ValueError as exc:
            raise HTTPException(404,str(exc)) from exc
        except httpx.HTTPError as exc:
            logger.warning('Unable to fetch official requirements: %s',type(exc).__name__)
            raise HTTPException(502,'Official study requirements currently unavailable') from exc
    return build_followup_plan(profile,studies)

@app.post('/api/v1/intake/reassess',response_model=ReassessmentResponse)
async def intake_reassess(req: ReassessmentRequest):
    """Apply a shared answer to every linked trial; re-fetch original criteria by ID."""
    # Patient facts and the trial source are re-derived server-side.
    if req.mode==Mode.replay:
        if any(not trial_id.startswith('DEMO-') for trial_id in req.trial_ids):
            raise HTTPException(422,'Sandbox reassessment requires DEMO study IDs')
        known={t.nct_id:t for t in all_sandbox_trials()}
        if set(req.trial_ids)-set(known):raise HTTPException(404,'Synthetic study not found')
        studies=[known[trial_id] for trial_id in req.trial_ids]
    else:
        if any(not trial_id.startswith('NCT') for trial_id in req.trial_ids):
            raise HTTPException(422,'Live reassessment requires official NCT study IDs')
        try:
            studies=await fetch_trials_by_ids(req.trial_ids)
        except ValueError as exc:
            raise HTTPException(404,str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502,'Official study requirements unavailable') from exc
    try:
        return reassess(req.profile,studies,req.updates)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc


@app.post('/api/v1/profiles/parse',response_model=PatientProfile)
async def parse_profile(req:ProfileRequest,request:Request):
    # Public live-registry search must remain usable without AI credentials.
    # An explicitly supplied team token opts into the legacy model profiler;
    # normal quick descriptions use the deterministic parser.
    if req.mode==Mode.live and enabled('ENABLE_LIVE_AI') and request.headers.get('X-Live-Access-Token'):
        require_live_ai(request)
        try:return await llm_profile(req.description)
        except ValueError as e:raise HTTPException(422,str(e)) from e
    return deterministic_profile(req.description)

@app.post('/api/v1/trials/search',response_model=SearchResponse)
async def search(req:SearchRequest):
    if req.mode==Mode.replay:
        profile=profile_from_guided_or_text(req.profile)
        trials=sandbox_search(profile,req.limit)
        return SearchResponse(mode=req.mode,trials=trials,total_returned=len(trials),retrieval_method='synthetic_sandbox_bm25')
    # Rebuild canonical facts server-side; do not trust a client-modified diagnosis.
    profile=profile_from_guided_or_text(req.profile)
    if not profile.diagnosis:
        raise HTTPException(422,'Enter a condition in guided intake or use a recognized condition in the quick description')
    try:
        validate_condition(profile.diagnosis)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    try:
        studies=await search_trials(profile.diagnosis,limit=min(max(req.limit*7,50),100))
    except httpx.HTTPError as e:
        logger.warning('ClinicalTrials.gov request failed: %s',type(e).__name__)
        raise HTTPException(502,'ClinicalTrials.gov is temporarily unavailable; check your internet connection') from e
    trials=rank_trials(profile,studies)[:req.limit]
    return SearchResponse(mode=req.mode,trials=trials,total_returned=len(trials),retrieval_method='clinicaltrials_api_v2_bm25',
        disclaimer=f'Official ClinicalTrials.gov public data; {len(studies)} recruiting/not-yet-recruiting candidates examined. No eligibility is established.')

@app.get('/api/v1/trials/{nct_id}',response_model=TrialRecord)
async def get_trial(nct_id:str):
    if nct_id.startswith('DEMO-'):
        match=next((t for t in replay_trials() if t.nct_id==nct_id),None)
        if match:return match
        raise HTTPException(404,'Synthetic demonstration trial not found')
    try:return await fetch_trial(nct_id)
    except ValueError as e:raise HTTPException(422,str(e)) from e
    except httpx.HTTPStatusError as e:
        raise HTTPException(404 if e.response.status_code==404 else 502,'Official study not available') from e
    except httpx.HTTPError as e:raise HTTPException(502,'ClinicalTrials.gov unavailable') from e

@app.post('/api/v1/trials/assess',response_model=TrialAssessment)
async def assess(req:AssessRequest,request:Request):
    if req.mode==Mode.replay:
        profile=deterministic_profile(req.profile.description)
        if not is_original_sample(profile):
            raise HTTPException(422,'Custom sandbox descriptions are searchable but have no pre-authored eligibility decisions. Live AI requires separate opt-in.')
        a=next((x for x in replay_assessments() if x.nct_id==req.trial.nct_id),None)
        if not a:raise HTTPException(400,'No replay assessment for the selected study')
        return a
    if req.trial.source!='clinicaltrials.gov':
        raise HTTPException(422,'Live assessment requires an official public trial')
    require_live_ai(request)
    try:
        # Fetch fresh official source server-side; never trust client-submitted eligibility text.
        verified_trial=await fetch_trial(req.trial.nct_id)
        return await assess_live(req.profile,verified_trial)
    except httpx.HTTPError as e:
        raise HTTPException(502,'Upstream service unavailable') from e

@app.post('/api/v1/analysis/run',response_model=AnalysisResponse)
async def run_analysis(req:AnalysisRequest,request:Request):
    start=time.perf_counter()
    if req.mode==Mode.replay:
        profile=profile_from_guided_or_text(req.profile)
        original=is_original_sample(profile)
        trials=(replay_trials()[:req.limit] if original else sandbox_search(profile,req.limit))
        ids={t.nct_id for t in trials}
        assessments=([a for a in replay_assessments() if a.nct_id in ids] if original else [])
        return AnalysisResponse(mode=req.mode,profile=profile,trials=trials,assessments=assessments,
             timings_ms={'sandbox_load':round((time.perf_counter()-start)*1000,2)},
             disclaimer=('Synthetic fixed replay with pre-authored educational assessments.' if original else
                         'Interactive fictional trial discovery only. No eligibility or skeptic judgments have been performed.'))
    require_live_ai(request)
    if not req.profile.diagnosis:
        raise HTTPException(422,'Verified synthetic diagnosis is required')
    try:studies=await search_trials(req.profile.diagnosis,limit=min(req.limit*5,30))
    except httpx.HTTPError as e:raise HTTPException(502,'ClinicalTrials.gov unavailable') from e
    ranked=rank_trials(req.profile,studies)[:min(req.limit,MAX_TRIALS)]
    retrieval_ms=round((time.perf_counter()-start)*1000,2)
    assessed=[]
    for trial in ranked:
        assessed.append(await assess_live(req.profile,trial))
    return AnalysisResponse(mode=req.mode,profile=req.profile,trials=ranked,assessments=assessed,
       timings_ms={'retrieval':retrieval_ms,'total':round((time.perf_counter()-start)*1000,2)})

@app.get('/api/v1/monitor/snapshot')
def monitor_snapshot():
    return {'mode':'replay','changes':[],'note':'Monitoring is not active; no real alerts are being claimed.'}

@app.get('/api/v1/evaluation/summary')
def evaluation_summary():
    return {'status':'not_measured','experiments':[],
            'message':'No benchmark or security experiments have been run. Do not interpret replay fixtures as measurements.'}

# MVP 2.0 five-role orchestrated matching; existing v1 routes remain intact.
from .agents.api import router as five_agent_router
app.include_router(five_agent_router)
