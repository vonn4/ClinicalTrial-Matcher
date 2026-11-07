import type { Analysis, Mode, PatientProfile, Trial } from '../types';
export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
async function post<T>(route:string,body:unknown,token?:string):Promise<T>{
  const controller = new AbortController();
  const timer = setTimeout(()=>controller.abort(), 120000);
  try {
    const r=await fetch(`${API_BASE}${route}`,{method:'POST',headers:{'Content-Type':'application/json',...(token?{'X-Live-Access-Token':token}:{})},body:JSON.stringify(body),signal:controller.signal});
    if(!r.ok){let message=`Request failed (${r.status})`;try{const x=await r.json();message=typeof x.detail==='string'?x.detail:message;}catch{/* non JSON */}throw new Error(message);}
    return await r.json() as T;
  }finally{clearTimeout(timer);}
}
export function parseProfile(description:string,mode:Mode,token?:string):Promise<PatientProfile>{return post('/api/v1/profiles/parse',{description,mode},token);}
export function searchTrials(profile:PatientProfile,mode:Mode):Promise<{trials:Trial[]}>{return post('/api/v1/trials/search',{profile,mode,limit:12});}
export function analyze(profile:PatientProfile,mode:Mode,token?:string):Promise<Analysis>{return post('/api/v1/analysis/run',{profile,mode,limit:3},token);}
