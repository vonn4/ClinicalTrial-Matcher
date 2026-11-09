import {BrainCircuit,CheckCircle2,ShieldCheck,Info} from 'lucide-react';
import type {AgentResult} from '../lib/agentApi';

const LABELS={
  profile:'Patient Profile',discovery:'Trial Discovery',analyst:'Eligibility Analyst',
  skeptic:'Independent Skeptic',clarification:'Clarification'
};
export default function AgentWorkflow({result}:{result:AgentResult|null}){
  if(!result)return null;
  const modelStages=result.trace.filter(stage=>stage.execution==='model').length;
  return <section className="panel agent-workflow" aria-label="Five-agent matching execution trace">
    <div className="agent-workflow-heading">
      <div><div className="section-eyebrow"><BrainCircuit size={15}/> FIVE-AGENT RESEARCH WORKFLOW · MVP 2.0</div>
        <h2>Matching execution trace</h2>
        <p>Every submitted search runs the five-stage workflow automatically. These are agent roles, not five separately detected AI models.</p></div>
      <span className="followup-phase-tag">Evidence-grounded</span>
    </div>
    <div className="agent-trace">
      <div className="agent-trace-heading"><ShieldCheck size={18}/><strong>Latest execution</strong>
        <span>{result.trace.length} roles · {modelStages} used AI · {result.model_calls} model calls · {result.candidate_count} candidates</span></div>
      {result.trace.map(stage=><div className="agent-trace-row" key={stage.agent}>
        <div className="agent-trace-icon"><CheckCircle2 size={17}/></div>
        <div className="agent-trace-content"><b>{LABELS[stage.agent]}</b><p>{stage.summary}</p>
          <small>{stage.execution==='model'?'Gemini inference invoked':stage.execution==='tools'?'Controlled tools / rules only':stage.execution==='skipped'?'No operation required':'Stage failed'} · {stage.model_calls} API calls · {stage.duration_ms.toFixed(0)} ms</small>
          <div className="agent-stage-metrics">{Object.entries(stage.details).filter(([key,value])=>key!=='model_invoked' &&
            (typeof value==='number'||typeof value==='boolean')).slice(0,4).map(([key,value])=>
              <span key={key}>{key.replace(/_/g,' ')}: {String(value)}</span>)}</div>
        </div>
      </div>)}
      {result.profile_concerns?.length>0&&<div className="agent-concerns">
        <strong>Profile Agent — suggested items to review</strong>
        <ul>{result.profile_concerns.map((note,i)=><li key={i}>{note}</li>)}</ul>
        <small>These suggestions are not confirmed facts or clinical assessments.</small>
      </div>}
      <div className="agent-result-note"><Info size={15}/>{result.notice}</div>
    </div>
  </section>;
}
