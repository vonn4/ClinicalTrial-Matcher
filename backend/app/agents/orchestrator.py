"""Five-role bounded orchestration; the Python controller owns all state transitions.

The system always executes all five role boundaries. Only explicitly opted-in
runs may invoke a language model, and every model call is budgeted. Deterministic
fallbacks are labeled as tools, NOT as model/agent inference accomplishments.
"""
from __future__ import annotations
import time
from ..schemas import Mode, PatientProfile
from .contracts import AgentRunRequest, AgentRunResponse, AgentTrace
from .budget import AgentBudget
from . import profile_agent, discovery_agent, analyst_agent, skeptic_agent, clarification_agent


def event(name, execution, summary, start, budget_before, budget, details=None):
    return AgentTrace(agent=name, execution=execution, summary=summary,
        duration_ms=round((time.perf_counter()-start)*1000, 2),
        model_calls=budget.calls-budget_before,
        details={k:v for k,v in (details or {}).items()
                 if isinstance(v,(str,int,float,bool))})


async def execute(request: AgentRunRequest, *, model_authorized: bool = False) -> AgentRunResponse:
    """Run a complete analysis; profile/criteria contents are never logged or persisted."""
    use_model = request.depth == 'model' and model_authorized
    budget = AgentBudget(maximum=9)
    trace: list[AgentTrace] = []

    t=time.perf_counter(); calls=budget.calls
    try:
        profile, meta = await profile_agent.execute(request.profile, model=use_model, budget=budget)
        fallback = False
    except Exception as exc:
        if not use_model: raise
        profile, meta = await profile_agent.execute(request.profile, model=False, budget=budget)
        fallback = True
    profile_meta_concerns = meta.get('concerns', [])
    trace.append(event('profile','tools' if fallback or not meta['model_invoked'] else 'model',
        'Canonical facts rebuilt; model suggestions never overwrite confirmed answers.' +
        (' Model unavailable; used verified input only.' if fallback else ''),t,calls,budget,meta))

    t=time.perf_counter();calls=budget.calls
    try:
        studies,meta=await discovery_agent.execute(profile,request.mode,count=(request.max_studies if request.study_ids else 12),
            selected_ids=request.study_ids,model=use_model,budget=budget)
        fallback=False
    except (ValueError,):
        raise  # malformed query or source IDs must never fall back silently
    except Exception as exc:
        # Model failures may fall back to the same real registry search, but
        # upstream network failures must propagate, never show made-up trials.
        from ..llm import ModelUnavailable
        from .budget import AgentBudgetExceeded
        if not use_model or not isinstance(exc,(ModelUnavailable,AgentBudgetExceeded)):
            raise
        studies,meta=await discovery_agent.execute(profile,request.mode,count=(request.max_studies if request.study_ids else 12),
            selected_ids=request.study_ids,model=False,budget=budget)
        fallback=True
    trace.append(event('discovery','tools' if fallback or not meta['model_invoked'] else 'model',
        'Candidate studies resolved from the requested source; search probes are not additional diagnoses.',
        t,calls,budget,meta))

    # Broad candidate display, but no more than three agent-reviewed studies.
    shortlist = studies[:request.max_studies]
    t=time.perf_counter();calls=budget.calls
    try:
        primary,meta=await analyst_agent.execute(profile,shortlist,model=use_model,budget=budget)
        fallback=False
    except Exception:
        if not use_model:raise
        primary,meta=await analyst_agent.execute(profile,shortlist,model=False,budget=budget)
        fallback=True
    trace.append(event('analyst','tools' if fallback or not meta['model_invoked'] else 'model',
        'Source-linked preliminary criterion judgments; complex or unsupported rules remain unresolved.'+
        (' Model failed; deterministic review used.' if fallback else ''),t,calls,budget,meta))

    t=time.perf_counter();calls=budget.calls
    try:
        reviewed,meta=await skeptic_agent.execute(profile,shortlist,primary,model=use_model,budget=budget)
        fallback=False
    except Exception:
        if not use_model:raise
        reviewed,meta=await skeptic_agent.execute(profile,shortlist,primary,model=False,budget=budget)
        fallback=True
    trace.append(event('skeptic','tools' if fallback or not meta['model_invoked'] else 'model',
        ('Independent model assessment compared with primary judgments.' if meta['model_invoked'] else
         'Deterministic source-integrity check only; independent model review NOT performed.'),
        t,calls,budget,meta))

    t=time.perf_counter();calls=budget.calls
    try:
        followups,meta=await clarification_agent.execute(profile,shortlist,model=use_model,budget=budget)
        fallback=False
    except Exception:
        if not use_model:raise
        followups,meta=await clarification_agent.execute(profile,shortlist,model=False,budget=budget)
        fallback=True
    trace.append(event('clarification','tools' if fallback or not meta['model_invoked'] else 'model',
        'Existing source-grounded questions prioritized and deduplicated by fact key.'+
        (' Model prioritization failed; deterministic ordering retained.' if fallback else ''),
        t,calls,budget,meta))

    profile_concerns = [v for v in profile_meta_concerns if isinstance(v,str) and v.strip()][:5]
    agent_completed = sum(1 for stage in trace if stage.execution=='model')
    return AgentRunResponse(mode=request.mode,profile=profile,trials=studies,assessments=reviewed,
        followups=followups,trace=trace,model_calls=budget.calls,
        candidate_count=int(trace[1].details.get('candidate_count',len(studies))),
        profile_concerns=profile_concerns,
        notice=(f'Five agent roles executed; {agent_completed} used model inference, '
                f'{5-agent_completed} used controlled tools. This is preliminary research navigation, '
                'not clinical eligibility. All patients must be fictional.'))
