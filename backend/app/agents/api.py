"""Public five-agent matching routes with strict model opt-in and no patient persistence."""
from fastapi import APIRouter, HTTPException, Request
import os
import httpx
from ..access import require_live_ai
from ..clinicaltrials import fetch_trials_by_ids
from ..reassessment import reassess
from ..sandbox import all_sandbox_trials
from ..schemas import Mode
from ..settings import enabled, GEMINI_MODEL, GEMINI_PROFILE_MODEL
from ..llm import ModelUnavailable
from .contracts import AgentRunRequest, AgentRunResponse, AgentClarifyRequest
from .budget import AgentBudgetExceeded
from .orchestrator import execute

router = APIRouter(prefix='/api/v1/matching', tags=['five-agent matching'])

def model_readiness() -> tuple[bool, str]:
    if not enabled('ENABLE_LIVE_AI'):
        return False, 'ENABLE_LIVE_AI is false in the backend environment'
    provider = os.getenv('AI_PROVIDER', 'gemini').strip().lower()
    if provider == 'openai':
        if not os.getenv('OPENAI_API_KEY', '').strip():
            return False, 'OPENAI_API_KEY is missing from the backend environment'
        if not enabled('OPENAI_ALLOW_BILLABLE'):
            return False, 'OPENAI_ALLOW_BILLABLE=true is required for potentially billable API requests'
    elif provider == 'gemini':
        if not os.getenv('GEMINI_API_KEY', '').strip():
            return False, 'GEMINI_API_KEY is missing from the backend environment'
    else:
        return False, 'AI_PROVIDER must be gemini or openai'
    if len(os.getenv('LIVE_AI_ACCESS_TOKEN', '')) < 16:
        return False, 'LIVE_AI_ACCESS_TOKEN must be at least 16 characters'
    return True, f'{provider.title()} configured locally; a team token is required for model requests'

@router.get('/capabilities')
def capabilities():
    ready, message = model_readiness()
    provider = os.getenv('AI_PROVIDER', 'gemini').strip().lower()
    openai = provider == 'openai'
    return {'contract_version':'2.0-A', 'agent_roles':['profile','discovery','analyst','skeptic','clarification'],
        'tools_available':True, 'live_model_enabled':enabled('ENABLE_LIVE_AI'),
        'model_ready':ready,'model_readiness_message':message,
        'model_provider':'OpenAI' if openai else 'Google Gemini' if provider == 'gemini' else 'Unknown',
        'analysis_model':os.getenv('OPENAI_MODEL', 'gpt-4.1-mini') if openai else GEMINI_MODEL,
        'profile_model':os.getenv('OPENAI_MODEL', 'gpt-4.1-mini') if openai else GEMINI_PROFILE_MODEL,
        'max_studies':3, 'max_model_calls_per_run':9, 'patient_persistence':False,
        'notice':'Configured model names do not prove successful inference. Check the execution trace after running.'}

async def _execute(req: AgentRunRequest, request: Request) -> AgentRunResponse:
    if req.depth=='model':
        ready, reason = model_readiness()
        if not ready:
            raise HTTPException(status_code=503, detail=f'Model-assisted analysis unavailable: {reason}')
        require_live_ai(request)
    try:
        return await execute(req,model_authorized=req.depth=='model')
    except AgentBudgetExceeded as exc:
        raise HTTPException(status_code=429,detail=str(exc)) from exc
    except (ValueError, ) as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502,detail='Official clinical-trial registry unavailable; no fictional studies substituted') from exc
    except (ModelUnavailable,) as exc:
        raise HTTPException(status_code=503,detail=str(exc)) from exc

@router.post('/analyze',response_model=AgentRunResponse)
async def analyze(req: AgentRunRequest, request: Request):
    return await _execute(req,request)

@router.post('/clarify',response_model=AgentRunResponse)
async def clarify(req: AgentClarifyRequest, request: Request):
    # Preserve the shortlist so a new patient fact cannot silently switch
    # the subject to entirely different studies during a clarification pass.
    if not req.study_ids:
        raise HTTPException(422,'Clarification requires the original official or synthetic trial IDs')
    if req.depth=='model':
        ready, reason = model_readiness()
        if not ready:
            raise HTTPException(status_code=503, detail=f'Model-assisted analysis unavailable: {reason}')
        require_live_ai(request)
    try:
        if req.mode==Mode.replay:
            known={t.nct_id:t for t in all_sandbox_trials()}
            if any(n not in known for n in req.study_ids):
                raise ValueError('Unknown synthetic study ID')
            studies=[known[n] for n in req.study_ids]
        else:
            studies=await fetch_trials_by_ids(req.study_ids)
        corrected=reassess(req.profile, studies, req.updates)
        # A correction invalidates old judgments; independent agents assess
        # the corrected snapshot again, bounded by the same model-call caps.
        next_req=AgentRunRequest(profile=corrected.profile, mode=req.mode,
            depth=req.depth,max_studies=req.max_studies,study_ids=req.study_ids)
        result=await execute(next_req,model_authorized=req.depth=='model')
        result.changed_criteria=corrected.changed_criteria
        return result
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502,'Official registry unavailable; existing studies not silently replaced') from exc
