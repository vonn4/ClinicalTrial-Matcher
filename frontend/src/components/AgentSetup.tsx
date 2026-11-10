import {useEffect,useState} from 'react';
import {BrainCircuit,Info,ShieldCheck} from 'lucide-react';
import {getAgentCapabilities} from '../lib/agentApi';
import type {AgentCapabilities,AgentDepth} from '../lib/agentApi';

interface Props{
  depth:AgentDepth;
  onDepthChange:(depth:AgentDepth)=>void;
  token:string;
  onTokenChange:(token:string)=>void;
  disabled:boolean;
  maxStudies:number;
  onMaxStudiesChange:(value:number)=>void;
}
export default function AgentSetup({depth,onDepthChange,token,onTokenChange,disabled,maxStudies,onMaxStudiesChange}:Props){
  const [capabilities,setCapabilities]=useState<AgentCapabilities|null>(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    let active=true;
    getAgentCapabilities().then(data=>{if(active){setCapabilities(data);setError('');}})
      .catch(exc=>{if(active)setError(exc instanceof Error?exc.message:'Cannot check model availability')});
    return ()=>{active=false;};
  },[]);
  const ready=capabilities?.model_ready===true;
  return <section className="panel agent-setup" aria-label="Select analysis mode before searching">
    <div className="agent-setup-heading"><BrainCircuit size={18}/>
      <div><strong>Analysis mode</strong>
        
      </div>
    </div>
    <div className="agent-mode-options" role="group" aria-label="Choose inference for the next matching search">
      <label><input type="radio" name="search-analysis-mode" value="tools"
        checked={depth==='tools'} disabled={disabled} onChange={()=>onDepthChange('tools')}/>
        Free tool-only review</label>
      <label><input type="radio" name="search-analysis-mode" value="model"
        checked={depth==='model'} disabled={disabled||!ready} onChange={()=>onDepthChange('model')}/>
        Model-assisted five-agent workflow</label>
    </div>
    {error?<p className="agent-readiness-warning" role="status">{error}. Tool-only analysis is available.</p>
      :capabilities===null?<p className="agent-readiness-note" role="status">Checking the backend model configuration…</p>
      :ready?<p className="agent-readiness-note"><ShieldCheck size={14}/> {capabilities.model_provider} ({capabilities.analysis_model}) configured. Model access is not yet verified; the trace reports actual calls.</p>
      :<p className="agent-readiness-warning"><Info size={14}/> {capabilities.model_provider} unavailable: {capabilities.model_readiness_message}. Check the selected provider and restart the backend after updating its configuration.</p>}
    {depth==='model'&&ready&&<div className="agent-token">
      <label htmlFor="model-study-count">Studies for full AI analysis</label>
      <select id="model-study-count" value={maxStudies} disabled={disabled}
        onChange={e=>onMaxStudiesChange(Number(e.target.value))}>
        <option value={1}>1 study — recommended for CPU</option>
        <option value={2}>2 studies — slower</option>
        <option value={3}>3 studies — may take several minutes</option>
      </select>
      <span>Other discovered studies remain visible, but only this many receive full Analyst/Skeptic review.</span>
    </div>}
    {depth==='model'&&ready&&<div className="agent-token">
      <label htmlFor="matching-team-token">Local team access token</label>
      <input id="matching-team-token" type="password" autoComplete="off"
        value={token} onChange={e=>onTokenChange(e.target.value)}
        disabled={disabled} placeholder="Your LIVE_AI_ACCESS_TOKEN (not an API provider key)"/>
      <span>Enter the browser team token, never your OpenAI API key. Kept only in this page.</span>
    </div>}
    
  </section>;
}
