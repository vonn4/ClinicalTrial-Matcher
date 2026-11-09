import {useState} from 'react';
import {BrainCircuit,CheckCircle2,AlertTriangle,Loader2,ShieldCheck,Play,Info} from 'lucide-react';
import type {Mode,PatientProfile} from '../types';
import {runFiveAgents} from '../lib/agentApi';
import type {AgentResult,AgentSettings} from '../lib/agentApi';

interface Props {
  mode:Mode;
  profile:PatientProfile;
  result:AgentResult|null;
  onCompleted:(result:AgentResult,settings:AgentSettings)=>void;
}
const LABELS={profile:'Patient Profile',discovery:'Trial Discovery',analyst:'Eligibility Analyst',skeptic:'Independent Skeptic',clarification:'Clarification'};
export default function AgentWorkflow({mode,profile,result,onCompleted}:Props){
  const [depth,setDepth]=useState<'tools'|'model'>('tools');
  const [token,setToken]=useState('');
  const [working,setWorking]=useState(false);
  const [error,setError]=useState('');
  async function run(){
    if(working)return;
    setError('');setWorking(true);
    try{
      const settings:AgentSettings={depth,token};
      const output=await runFiveAgents(profile,mode,settings);
      onCompleted(output,settings);
    }catch(e){setError(e instanceof Error?e.message:'Unable to run matching workflow');}
    finally{setWorking(false);}
  }
  return <section className="panel agent-workflow" aria-label="Five-agent matching workflow">
    <div className="agent-workflow-heading">
      <div><div className="section-eyebrow"><BrainCircuit size={15}/> FIVE-AGENT RESEARCH WORKFLOW · MVP 2.0</div>
        <h2>Agent-driven trial matching</h2>
        <p>Profile, discovery, analyst, independent skeptic and clarification are distinct, auditable stages.</p></div>
      <span className="followup-phase-tag">Evidence-grounded</span>
    </div>
    <div className="agent-mode-options" role="group" aria-label="Analysis execution depth">
      <label><input type="radio" name="agent-depth" checked={depth==='tools'} onChange={()=>setDepth('tools')}/> Free tool-only analysis</label>
      <label><input type="radio" name="agent-depth" checked={depth==='model'} onChange={()=>setDepth('model')}/> Model-assisted analysis (team opt-in)</label>
    </div>
    {depth==='model'&&<div className="agent-token"><label htmlFor="agent-team-token">TEAM ACCESS TOKEN</label>
      <input id="agent-team-token" type="password" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)}
        placeholder="Required by a locally enabled, free-tier Gemini backend"/>
      <span>No billing upgrade or automatic paid fallback. Synthetic profiles only.</span></div>}
    <div className="agent-workflow-action">
      <button type="button" className="primary-button" onClick={()=>void run()}
        disabled={working||!profile.diagnosis||(depth==='model'&&!token.trim())}>
        {working?<Loader2 className="spin" size={16}/>:<Play size={16}/>}
        {working?'Running stages…':'Run five-agent workflow'}
      </button>
      <span>{mode==='live'?'Official ClinicalTrials.gov studies':'Fictional sandbox studies'} · up to 3 analyzed</span>
    </div>
    {error&&<div className="intake-error" role="alert"><AlertTriangle size={16}/> {error}</div>}
    {result&&<div className="agent-trace">
      <div className="agent-trace-heading"><ShieldCheck size={18}/><strong>Latest execution trace</strong>
        <span>{result.model_calls} model calls · {result.candidate_count} candidates examined</span></div>
      {result.trace.map(stage=><div className="agent-trace-row" key={stage.agent}>
        <div className="agent-trace-icon"><CheckCircle2 size={17}/></div>
        <div className="agent-trace-content"><b>{LABELS[stage.agent]}</b><p>{stage.summary}</p>
          <small>{stage.execution==='model'?'Model reasoning invoked':stage.execution==='tools'?'Controlled tools / rules, no model':'Not completed'} · {stage.model_calls} calls · {stage.duration_ms.toFixed(0)} ms</small>
          <div className="agent-stage-metrics">{Object.entries(stage.details).filter(([key,value])=>key!=='model_invoked' && (typeof value==='number' || typeof value==='boolean')).slice(0,4).map(([key,value])=><span key={key}>{key.replace(/_/g,' ')}: {String(value)}</span>)}</div>
        </div>
      </div>)}
      {result.profile_concerns?.length>0&&<div className="agent-concerns">
        <strong>Profile Agent — unverified concerns to review</strong>
        <ul>{result.profile_concerns.map((note,i)=><li key={i}>{note}</li>)}</ul>
        <small>These are suggestions only. Confirm or correct the guided profile before relying on them.</small>
      </div>}
      <div className="agent-result-note"><Info size={15}/>{result.notice}</div>
    </div>}
  </section>;
}
