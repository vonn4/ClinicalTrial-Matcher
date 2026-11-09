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
}
export default function AgentSetup({depth,onDepthChange,token,onTokenChange,disabled}:Props){
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
        <p>Submitting the patient intake automatically runs all five workflow stages once. No separate Play action.</p>
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
      :ready?<p className="agent-readiness-note"><ShieldCheck size={14}/> Gemini configured: profile <code>{capabilities.profile_model}</code>, reasoning <code>{capabilities.analysis_model}</code>. Successful inference is verified by the execution trace.</p>
      :<p className="agent-readiness-warning"><Info size={14}/> Gemini not enabled: {capabilities.model_readiness_message}. Add the required values to the project <code>.env</code>, then restart the app and refresh this page.</p>}
    {depth==='model'&&ready&&<div className="agent-token">
      <label htmlFor="matching-team-token">Local team access token</label>
      <input id="matching-team-token" type="password" autoComplete="off"
        value={token} onChange={e=>onTokenChange(e.target.value)}
        disabled={disabled} placeholder="Your LIVE_AI_ACCESS_TOKEN (not the Gemini API key)"/>
      <span>Kept in the page's temporary state, not stored in the browser. Only fictional patient details. Model calls use the configured free-tier project.</span>
    </div>}
    <p className="agent-readiness-note">Five agent roles do not mean five separate models or five guaranteed LLM calls. The Profile, Discovery and Clarification agents call Gemini only when their inputs require it; the Analyst and Skeptic use independent reasoning where supported.</p>
  </section>;
}
