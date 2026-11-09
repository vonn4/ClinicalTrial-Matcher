import type {Mode,PatientProfile,Trial,TrialAssessment,FollowupPlan,CriterionDelta,IntakeAnswer} from '../types';
import {API_BASE} from './api';

export interface AgentTrace {
  agent: 'profile'|'discovery'|'analyst'|'skeptic'|'clarification';
  execution: 'model'|'tools'|'skipped'|'failed';
  summary: string;
  duration_ms:number;
  model_calls:number;
  details:Record<string,number|string|boolean>;
}
export interface AgentResult {
  contract_version:string;
  mode:Mode;
  profile:PatientProfile;
  trials:Trial[];
  assessments:TrialAssessment[];
  followups:FollowupPlan;
  trace:AgentTrace[];
  candidate_count:number;
  profile_concerns:string[];
  model_calls:number;
  changed_criteria:CriterionDelta[];
  notice:string;
}
export type AgentDepth = 'tools'|'model';
export interface AgentSettings {depth:AgentDepth; token:string}

async function request<T>(path:string,body:object,token:string):Promise<T> {
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),120000);
  try {
    const response=await fetch(`${API_BASE}${path}`,{
      method:'POST',signal:controller.signal,
      headers:{'Content-Type':'application/json',...(token?{'X-Live-Access-Token':token}:{})},
      body:JSON.stringify(body)
    });
    if(!response.ok){
      let message=`Request failed (${response.status})`;
      try{const parsed=await response.json();if(typeof parsed.detail==='string')message=parsed.detail;}catch{/* HTTP response not JSON */}
      throw new Error(message);
    }
    return await response.json() as T;
  }finally{clearTimeout(timer);}
}
export function runFiveAgents(profile:PatientProfile,mode:Mode,settings:AgentSettings):Promise<AgentResult>{
  return request('/api/v1/matching/analyze',{profile,mode,depth:settings.depth,max_studies:3},settings.token);
}
export function clarifyFiveAgents(profile:PatientProfile,mode:Mode,study_ids:string[],updates:Record<string,IntakeAnswer>,settings:AgentSettings):Promise<AgentResult>{
  return request('/api/v1/matching/clarify',{profile,mode,depth:settings.depth,max_studies:Math.min(3,study_ids.length),study_ids,updates},settings.token);
}
