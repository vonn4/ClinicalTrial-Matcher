import {AlertTriangle,CheckCircle2,Download,Info,ShieldCheck} from 'lucide-react';
import type {AgentResult,AgentTrace} from '../lib/agentApi';

const LABELS:Record<AgentTrace['agent'],string>={
  profile:'Patient profile',discovery:'Trial discovery',analyst:'Eligibility analyst',
  skeptic:'Independent skeptic',clarification:'Follow-up questions'
};
function failed(stage:AgentTrace):boolean{
  return Number(stage.details.model_failures||0)>0||Number(stage.details.budget_skips||0)>0||
    stage.details.model_fallback===true||(stage.model_calls>0&&stage.execution!=='model');
}
function saveRunMetrics(result:AgentResult):void{
  // Evidence export intentionally contains no patient profile, criteria text,
  // history, model prompt, browser access token, or private configuration.
  const data={
    schema:'clinicaltrial-matcher-metrics-v1',
    source:'browser_observed_local_run',
    exported_at:new Date().toISOString(),
    sample_count:1,
    model_calls:result.model_calls,
    ai_assisted_stages:result.trace.filter(t=>t.execution==='model').length,
    total_stage_ms:Math.round(result.trace.reduce((sum,t)=>sum+t.duration_ms,0)),
    stages:result.trace.map(t=>({
      agent:t.agent,execution:t.execution,duration_ms:t.duration_ms,model_calls:t.model_calls,
      model_failures:typeof t.details.model_failures==='number'?t.details.model_failures:0
    })),
    studies:result.assessments.map(a=>({
      nct_id:a.nct_id,summary:a.summary,criteria_count:a.criteria.length,
      unresolved_count:a.unresolved.length,skeptic_disagreements:a.skeptic.filter(f=>f.disagreement).length,
      independent_skeptic_criteria:a.skeptic.length
    }))
  };
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=document.createElement('a');
  link.href=url;
  link.download='clinicaltrial-matcher-run-metrics.json';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export default function AgentWorkflow({result}:{result:AgentResult|null}){
  if(!result)return null;
  const modelStages=result.trace.filter(x=>x.execution==='model').length;
  const failures=result.trace.filter(failed);
  const locationStatus=result.trace.find(x=>x.agent==='discovery')?.details.location_filter_status;
  return <section className="panel agent-workflow" aria-label="Five-agent matching execution trace">
    <div className="agent-workflow-heading"><div>
      <h2>Matching execution trace</h2>
      <p>{result.trace.length} stages completed automatically; AI is optional, and failed calls do not count as completed reviews.</p>
      <button type="button" className="secondary-button" onClick={()=>saveRunMetrics(result)}>
        <Download size={14}/> Export anonymous timing evidence
      </button>
    </div></div>
    <div className="agent-trace">
      <div className="agent-trace-heading"><ShieldCheck size={18}/><strong>Execution summary</strong>
        <span>{result.trace.length} stages · {modelStages} AI-assisted · {result.model_calls} model {result.model_calls===1?'attempt':'attempts'} · {result.trials.length} matched studies · {(result.trace.reduce((sum,t)=>sum+t.duration_ms,0)/1000).toFixed(1)}s pipeline</span></div>
      {typeof locationStatus==='string'&&<div className="agent-result-note" role="status">
        <Info size={15}/><span><strong>Location search:</strong> {locationStatus}</span>
      </div>}
      {failures.length>0&&<div className="agent-error-banner" role="alert">
        <AlertTriangle size={17}/><span>{failures.length} AI stage(s) had problems. No failed model review is counted as verified; review details below.</span>
      </div>}
      {result.trace.map(stage=><div className="agent-trace-row" key={stage.agent}>
        <div className={'agent-trace-icon '+(failed(stage)?'agent-warning':'')}>
          {failed(stage)?<AlertTriangle size={17}/>:<CheckCircle2 size={17}/>}
        </div>
        <div className="agent-trace-content">
          <b>{LABELS[stage.agent]}</b>
          <small>{Number(stage.details.budget_skips||0)>0?'Partial AI coverage; other studies use rules-only review':failed(stage)?'AI unavailable; fallback used':stage.execution==='model'?'AI review completed':stage.execution==='tools'?'Rules / tools only':stage.execution==='skipped'?'No review required':'Stage failed'} · {stage.model_calls} model call{stage.model_calls===1?'':'s'}</small>
          {failed(stage)&&<p className="agent-error-detail">
            {Number(stage.details.budget_skips||0)>0?
              `${stage.details.budget_skips} study/studies used rules-only review to reserve independent Skeptic capacity. ${typeof stage.details.model_help==='string'?stage.details.model_help:''}`:
              typeof stage.details.model_help==='string'?stage.details.model_help:'AI inference failed; inspect the configured model and provider access.'}
            {typeof stage.details.model_http_status==='number'?` (HTTP ${stage.details.model_http_status})`:''}
          </p>}
          <details className="agent-technical-details"><summary>Stage details</summary>
            <p>{stage.summary}</p>
            <small>{stage.duration_ms.toFixed(0)} ms</small>
            <div className="agent-stage-metrics">{Object.entries(stage.details).filter(([key,value])=>
              !['model_invoked','model_help'].includes(key)&&(typeof value==='number'||typeof value==='boolean'||typeof value==='string')).slice(0,9).map(([key,value])=>
                <span key={key}>{key.replace(/_/g,' ')}: {String(value)}</span>)}</div>
          </details>
        </div>
      </div>)}
      {result.profile_concerns?.length>0&&<div className="agent-concerns">
        <strong>Profile questions to review</strong>
        <ul>{result.profile_concerns.map((note,i)=><li key={i}>{note}</li>)}</ul>
      </div>}
      <div className="agent-result-note"><Info size={15}/>
        These are preliminary research checks, not clinical eligibility decisions.
      </div>
    </div>
  </section>;
}
