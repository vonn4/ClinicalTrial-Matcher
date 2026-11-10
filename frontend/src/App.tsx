import {useEffect,useMemo,useState} from 'react';
import {Activity,ArrowRight,BarChart3,Bookmark,Check,CheckCircle2,ChevronDown,ChevronRight,CircleAlert,ClipboardList,Download,ExternalLink,Filter,FlaskConical,HeartPulse,Info,MapPin,Microscope,RefreshCw,Search,ShieldCheck,SlidersHorizontal,X} from 'lucide-react';
import {Bar,BarChart,CartesianGrid,Cell,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import type {Analysis,CriterionDelta,FollowupPlan,IntakeAnswer,IntakeSubmission,Mode,Page,PatientProfile,ReassessmentResponse,Status,Summary,Trial,TrialAssessment} from './types';

import {parseProfile,buildIntakeProfile,getTrialFollowups,reassessTrials,checkLiveRegistry} from './lib/api';
import GuidedIntake from './components/GuidedIntake';
import TrialFollowups from './components/TrialFollowups';
import AgentWorkflow from './components/AgentWorkflow';
import AgentSetup from './components/AgentSetup';
import type {AgentDepth,AgentResult,AgentSettings} from './lib/agentApi';
import {runFiveAgents,clarifyFiveAgents} from './lib/agentApi';

const STATUS_LABEL:Record<Summary,string>={potential_match:'Potential match',needs_information:'Needs more information',identified_conflict:'Eligibility conflict',clinical_review:'Clinical review required'};
function emptyPatient():PatientProfile{
  return {description:'Synthetic patient intake not yet provided.',age:null,diagnosis:null,
    stage:null,biomarkers:[],treatments:[],location:null,facts:[],unknowns:[],synthetic:true};
}
function emptyAnalysis():Analysis{
  return {mode:'live',profile:emptyPatient(),trials:[],assessments:[],timings_ms:{},
    disclaimer:'Search official ClinicalTrials.gov studies using fictional patient details.'};
}
function requireOfficialStudies(trials:Trial[]):void{
  if(trials.some(t=>t.source!=='clinicaltrials.gov'||!/^NCT\d{8}$/.test(t.nct_id)))
    throw new Error('Unexpected non-registry study data. Live search results were not displayed.');
}
const CRITERION_LABEL:Record<Status,string>={met:'Met / present',not_met:'Not met / absent',unknown:'Unknown',clinical_review:'Clinical review'};
function slug(s:string){return s.toLowerCase().replace(/_/g,'-')}
function getStorage():string[]{try{const ids=JSON.parse(localStorage.getItem('ctm-saved')||'[]') as unknown;return Array.isArray(ids)?ids.filter((id):id is string=>typeof id==='string'&&/^NCT\d{8}$/.test(id)):[]}catch{return []}}

function DashboardHeader({connection}:{connection:string}){
  return <div className="top-header">
    <div><div className="crumb">CLINICAL TRIAL DISCOVERY</div><h1>Find clinical trials</h1><p>Search real studies and review the evidence behind each result.</p></div>
    <div className="header-side"><span className="live-dot"/><span>Official ClinicalTrials.gov</span><span className="header-sep"/> <span className="status-sub">{connection}</span></div>
  </div>;
}
function Metric({icon,label,value,sub,kind}:{icon:React.ReactNode,label:string,value:string|number,sub:string,kind?:string}){
  return <div className="metric"><div className="metric-top"><span className="metric-label">{label}</span><div className={'metric-icon '+(kind||'')}>{icon}</div></div><strong className="metric-number">{value}</strong><span className="metric-sub">{sub}</span></div>;
}
function SummaryBadge({summary}:{summary:Summary|undefined}){
  if(!summary)return <span className="summary-badge neutral"><Info size={13}/> Not assessed</span>;
  return <span className={'summary-badge '+slug(summary)}>{summary==='identified_conflict'?<CircleAlert size={13}/>:summary==='potential_match'?<CheckCircle2 size={13}/>:<Info size={13}/>} {STATUS_LABEL[summary]}</span>
}
function CritBadge({status,kind}:{status:Status;kind:string}){
  const label=kind==='exclusion'?(status==='met'?'Exclusion present':status==='not_met'?'Exclusion absent':CRITERION_LABEL[status]):CRITERION_LABEL[status];
  return <span className={'crit-badge '+(kind==='exclusion'&&status==='met'?'conflict':slug(status))}>{label}</span>
}
function Sidebar({page,setPage,savedCount}:{page:Page;setPage:(p:Page)=>void;savedCount:number}){
  const items=[{id:'discover',label:'Discover trials',icon:<Search size={18}/>},{id:'saved',label:'Saved & compare',icon:<Bookmark size={18}/>}];
  return <aside className="sidebar">
    <div className="brand"><div className="brand-icon"><HeartPulse size={24}/></div><div className="brand-copy"><strong>ClinicalTrial</strong><span>Matcher<span className="brand-dot">.</span></span></div></div>
    <div className="nav-label">WORKSPACE</div>
    <nav>{items.map(it=><button key={it.id} className={'nav-link '+(page===it.id?'active':'')} onClick={()=>setPage(it.id as Page)}>{it.icon}<span>{it.label}</span>{it.id==='saved'&&savedCount>0&&<span className="nav-count">{savedCount}</span>}</button>)}</nav>
    <div className="sidebar-spacer"/>
    <div className="sidebar-card"><div className="sidebar-card-head"><ShieldCheck size={16}/> SOURCE-LINKED REVIEW</div><p>Every finding links to study criteria. Unknown information stays unresolved.</p><div className="sidebar-signal"><span className="live-dot"/> Research prototype</div></div>
    <div className="sidebar-footer">HACKAROO 2026</div>
  </aside>;
}
function TrialCard({trial,assessment,selected,saved,onSelect,onSave}:{trial:Trial;assessment?:TrialAssessment;selected:boolean;saved:boolean;onSelect:()=>void;onSave:()=>void}){
  return <div className={'trial-card '+(selected?'selected':'')}>
    <div className="trial-card-top"><span className="trial-id">{trial.nct_id}</span><span className="study-source">OFFICIAL STUDY</span><button className={'icon-button save-icon '+(saved?'saved':'')} title={saved?'Remove from saved':'Save trial'} onClick={onSave}><Bookmark size={16} fill={saved?'currentColor':'none'}/></button></div>
    <button className="trial-title-button" onClick={onSelect}>{trial.title}<ChevronRight size={17}/></button>
    <div className="trial-tags"><span className="pill"><span className="small-dot"/>{trial.status.replaceAll('_',' ')}</span><span className="pill">{trial.phase.join(', ').replaceAll('_',' ')||'Phase unspecified'}</span>{trial.broad_registry&&<span className="pill">Broad registry</span>}</div>
    {trial.match_explanation&&<p className="trial-match-reason"><Info size={13}/>{trial.match_explanation}</p>}
    <div className="trial-card-meta"><MapPin size={14}/><span>{trial.locations[0]||'Location not listed'}</span></div>
    <div className="trial-card-bottom"><SummaryBadge summary={assessment?.summary}/><button className="text-link" onClick={onSelect}>Review <ArrowRight size={14}/></button></div>
  </div>;
}
function EligibilityDetail({trial,assessment}:{trial?:Trial;assessment?:TrialAssessment}){
  const [expanded,setExpanded]=useState<string|null>(null);
  useEffect(()=>setExpanded(null),[trial?.nct_id]);
  if(!trial)return <div className="empty-detail"><Microscope size={25}/><h3>Select a clinical trial</h3><p>Open any study to inspect the original requirements and the preliminary evidence review.</p></div>;
  const pairs=assessment?.criteria.map(c=>({c,a:assessment.assessments.find(a=>a.criterion_id===c.id),s:assessment.skeptic.find(s=>s.criterion_id===c.id)}))||[];
  const counts={inclusion:pairs.filter(x=>x.c.kind==='inclusion').length,exclusion:pairs.filter(x=>x.c.kind==='exclusion').length,unknown:pairs.filter(x=>x.a?.status==='unknown'||x.a?.status==='clinical_review').length};
  return <div className="detail-panel">
    <div className="section-eyebrow"><FlaskConical size={14}/> EVIDENCE REVIEW</div><h2>{trial.title}</h2>
    <div className="detail-meta"><span>ClinicalTrials.gov study</span><span>•</span><span>{trial.nct_id}</span><span>•</span><span>{trial.status.replaceAll('_',' ')}</span>{trial.updated&&<><span>•</span><span>Updated {trial.updated}</span></>}</div>
    {trial.match_explanation&&<div className="trial-match-detail"><Info size={15}/><div><strong>Why this study appeared</strong><p>{trial.match_explanation}{trial.broad_registry?' This is a broad registry, not necessarily a disease-specific trial; confirm its separate eligibility criteria.':''}</p></div></div>}
    <div className="detail-summary"><SummaryBadge summary={assessment?.summary}/><p>{assessment?.summary==='identified_conflict'?'A requirement conflicts with the provided synthetic profile.':assessment?.summary==='potential_match'?'No conflicts detected in this preliminary analysis; screening is still required.':assessment?.summary==='clinical_review'?'A requirement needs expert interpretation or independent screening; not confirmed eligible.':assessment?'Important information remains unresolved. Do not treat this as confirmed eligibility.':'This study has not been assessed. Relevance is not eligibility.'}</p></div>
    {assessment?<>
      <div className="mini-stats"><span><b>{counts.inclusion}</b> Inclusion</span><span><b>{counts.exclusion}</b> Exclusion</span><span><b>{counts.unknown}</b> Unresolved</span></div>
      <div className="subsection-label">CRITERION-BY-CRITERION ANALYSIS <span>{pairs.length} identified</span></div>
      <div className="criterion-list">{pairs.map(({c,a,s})=><div className="criterion" key={c.id}>
        <button className="criterion-header" onClick={()=>setExpanded(expanded===c.id?null:c.id)} aria-expanded={expanded===c.id}>
          <div className="criterion-names"><span className="criterion-id">{c.id}</span><span className="criterion-heading">{c.text}</span></div><div className="criterion-status">{a&&<CritBadge status={a.status} kind={c.kind}/>}<ChevronDown size={14} className={expanded===c.id?'rotate':''}/></div>
        </button>
        {expanded===c.id&&<div className="criterion-body"><div className="evidence-label">EXACT TRIAL REQUIREMENT</div><blockquote>“{c.source_text}”</blockquote><div className="evidence-label">ASSESSMENT</div><p>{a?.explanation||'Not assessed'}</p><div className="evidence-label">PATIENT EVIDENCE</div><p>{a?.patient_evidence?.length?a.patient_evidence.map(v=>`“${v}”`).join(' · '):'No verified patient evidence recorded.'}</p>{a?.question_for_doctor&&<div className="question"><Info size={14}/>{a.question_for_doctor}</div>}<div className="skeptic-row"><ShieldCheck size={14}/> {assessment.skeptic.length===0?'Independent AI skeptic not completed':`Independent review: ${s?.disagreement?'Disagreement flagged':s?'No disagreement recorded':'Criterion not independently reviewed'}`}</div></div>}
      </div>)}</div>
      <div className="review-footnote"><ShieldCheck size={16}/><span>{assessment.skeptic.length>0?'Independent model review completed for some criteria; human clinical screening still required.':assessment.provenance==='live_llm'?'AI analyst ran, but independent skeptic review was not completed for this study. Findings require review.':'Deterministic review of self-reported synthetic facts only. No AI skeptic or medical verification was performed.'}</span></div>
    </>:<div className="unassessed-criteria"><div className="empty-assessment"><Info size={17}/><span>No eligibility or skeptic assessment has been performed for this profile. Trial relevance alone does not imply eligibility. Authorized AI assessment requires optional free-tier model setup.</span></div><div className="evidence-label">ORIGINAL STUDY REQUIREMENTS — NOT EVALUATED</div><pre>{trial.eligibility_text || 'Eligibility criteria are not available in this trial record.'}</pre></div>}
    {trial.url&&<a className="official-link" href={trial.url} target="_blank" rel="noopener noreferrer">View original ClinicalTrials.gov study <ExternalLink size={14}/></a>}
    <div className="disclaimer-line">Research/navigation only • Not clinical advice • Study team determines eligibility</div>
  </div>;
}
function ResearchLab(){
  const planned=[{key:'nDCG@10',name:'Retrieval ranking'},{key:'Exclusion recall',name:'Eligibility safety'},{key:'Skeptic corrections',name:'Independent review'},{key:'Attack success',name:'Prompt injection'}];
  return <div className="research-content"><div className="section-eyebrow"><Microscope size={14}/> REPRODUCIBLE RESEARCH</div><h2>Evaluation laboratory</h2><p className="lead">Measurements will appear only after the corresponding benchmark experiments have been run. Internal test fixtures are not research findings.</p>
    <div className="metrics-grid">{planned.map(p=><Metric key={p.key} icon={<Activity size={18}/>} label={p.key} value="—" sub="Not measured"/>)}</div>
    <div className="research-grid"><div className="panel paper"><div className="panel-heading"><h3>Retrieval benchmark</h3><span className="subtle-tag">PLANNED</span></div><p>Compare BM25 against semantic/hybrid ranking on the historical TREC Clinical Trials snapshot, using the corresponding relevance judgments.</p><div className="research-placeholder"><BarChart3 size={28}/><strong>Awaiting measured benchmark results</strong><span>nDCG@10 • Precision@K • eligible-trial Recall@K</span></div></div><div className="panel paper"><div className="panel-heading"><h3>Safety & verification</h3><span className="subtle-tag">PLANNED</span></div><p>Evaluate criterion accuracy, missed exclusions, skeptical agent corrections, false-positive findings, and malicious retrieved text.</p><div className="research-placeholder"><ShieldCheck size={28}/><strong>Awaiting labeled test runs</strong><span>Confusion matrix • disagreements • attack outcomes</span></div></div></div>
    <div className="research-method"><h3>Evidence standards</h3><div className="method-cards"><div><strong>01 / Historical corpus</strong><p>Never substitute today's public registry for the original TREC benchmark snapshot.</p></div><div><strong>02 / Labeled cases</strong><p>Separate clinician-unverified synthetic criterion labels from genuine clinical expert annotations.</p></div><div><strong>03 / Exact provenance</strong><p>Record dataset version, model, prompt, sample size, response time and failures per run.</p></div></div></div>
  </div>;
}
function SavedView({trials,assessments,saved,setSaved,onSelect}:{trials:Trial[];assessments:TrialAssessment[];saved:string[];setSaved:(x:string[])=>void;onSelect:(x:string)=>void}){
  const matches=trials.filter(t=>saved.includes(t.nct_id));
  return <div className="saved-view"><div className="section-eyebrow"><Bookmark size={14}/> PATIENT WORKSPACE</div><h2>Saved trials & physician handoff</h2><p className="lead">Save candidate studies, compare preliminary findings, and prepare questions for a clinical discussion. Live mode uses real study IDs with synthetic patient information.</p>
    <div className="saved-toolbar"><div><b>{matches.length}</b> selected studies in this session</div><button className="primary-button" disabled={matches.length===0} onClick={()=>window.print()}><Download size={16}/> Print / Save report as PDF</button></div>
    {!matches.length?<div className="large-empty"><Bookmark size={29}/><h3>No saved studies</h3><p>Choose the bookmark icon on a trial to include it in your comparison and physician handoff summary.</p></div>:<div className="saved-list">{matches.map(t=>{const a=assessments.find(x=>x.nct_id===t.nct_id);return <div className="saved-row" key={t.nct_id}><div><span className="trial-id">{t.nct_id}</span><h3>{t.title}</h3><SummaryBadge summary={a?.summary}/></div><div className="saved-actions"><button onClick={()=>onSelect(t.nct_id)} className="secondary-button">Inspect <ArrowRight size={14}/></button><button className="icon-button" onClick={()=>setSaved(saved.filter(id=>id!==t.nct_id))}><X size={16}/></button></div></div>})}</div>}
    {matches.length>0&&<section className="print-report"><h2>Physician discussion brief — synthetic research example</h2><p>This report is a research/navigation aid. No eligibility or treatment advice is provided.</p>{matches.map(t=>{const a=assessments.find(x=>x.nct_id===t.nct_id);return <div key={t.nct_id}><h3>{t.nct_id}: {t.title}</h3><p>Preliminary status: {a?STATUS_LABEL[a.summary]:'Not assessed'}</p><p>Official source: {t.url||'Synthetic demonstration study, no official source'}</p>{a?.assessments.filter(x=>x.question_for_doctor).map(x=><p key={x.criterion_id}>Question ({x.criterion_id}): {x.question_for_doctor}</p>)}</div>})}</section>}
    <div className="notice"><Info size={16}/><p>Saved trial identifiers are stored only in this browser for demonstration. They are not synchronized to clinicians and no notification is sent.</p></div>
  </div>;
}

export default function App(){
  const [page,setPage]=useState<Page>('discover');
  const [intakeMode,setIntakeMode]=useState<'guided'|'quick'>('guided');
  const mode:Mode='live';
  const [text,setText]=useState('');
  const [profile,setProfile]=useState<PatientProfile>(emptyPatient);
  const [analysis,setAnalysis]=useState<Analysis>(emptyAnalysis);
  const [selected,setSelected]=useState('');
  const [saved,setSaved]=useState<string[]>(getStorage);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [connection,setConnection]=useState('Checking public registry');
  const [registryStatus,setRegistryStatus]=useState<{connected:boolean;api_version:string;data_timestamp:string}|null>(null);
  const [registryError,setRegistryError]=useState('');
  const [filter,setFilter]=useState('all');
  const [query,setQuery]=useState('');
  const [liveSearched,setLiveSearched]=useState(false);
  const [followupPlan,setFollowupPlan]=useState<FollowupPlan|null>(null);
  const [followupBusy,setFollowupBusy]=useState(false);
  const [followupError,setFollowupError]=useState('');
  const [review,setReview]=useState<ReassessmentResponse|null>(null);
  const [changedCriteria,setChangedCriteria]=useState<CriterionDelta[]>([]);
  const [answerBusy,setAnswerBusy]=useState(false);
  const [analysisDepth,setAnalysisDepth]=useState<AgentDepth>('tools');
  const [teamToken,setTeamToken]=useState('');
  const [agentResult,setAgentResult]=useState<AgentResult|null>(null);
  const [agentSettings,setAgentSettings]=useState<AgentSettings|null>(null);
  useEffect(()=>{
    let active=true;
    if(analysis.trials.length===0){setFollowupPlan(null);setReview(null);setFollowupBusy(false);setFollowupError('');return;}
    setFollowupPlan(null);setReview(null);setChangedCriteria([]);setFollowupError('');setFollowupBusy(true);
    if(agentResult){
      setReview({profile:agentResult.profile,assessments:agentResult.assessments,
        followups:agentResult.followups,changed_criteria:agentResult.changed_criteria,notice:agentResult.notice});
      setFollowupPlan(agentResult.followups);
      setChangedCriteria(agentResult.changed_criteria);
      setFollowupBusy(false);
      return;
    }
    const ids=analysis.trials.slice(0,8).map(t=>t.nct_id);
    // Preserve a completed opt-in LLM evaluation and the legacy fixed replay.
    // Guided cases get an initial partial deterministic review before follow-ups.
    const useReview=intakeMode==='guided' && !analysis.assessments.some(a=>a.provenance==='live_llm');
    const load=useReview ? reassessTrials(analysis.profile,analysis.mode,ids,{})
      .then(result=>{if(active){setReview(result);setFollowupPlan(result.followups);}})
      : getTrialFollowups(analysis.profile,analysis.mode,ids)
      .then(plan=>{if(active)setFollowupPlan(plan);});
    load.catch(err=>{if(active)setFollowupError(err instanceof Error?err.message:'Question planning unavailable');})
      .finally(()=>{if(active)setFollowupBusy(false);});
    return ()=>{active=false;};
  },[analysis,intakeMode,agentResult]);
  async function answerFollowup(factKey:string,answer:IntakeAnswer):Promise<boolean>{
    if(answerBusy||analysis.trials.length===0)return false;
    setAnswerBusy(true);setFollowupError('');
    try{
      const current=review?.profile??analysis.profile;
      if(agentResult && agentSettings){
        const ids=agentResult.assessments.map(a=>a.nct_id);
        const updated=await clarifyFiveAgents(current,analysis.mode,ids,{[factKey]:answer},agentSettings);
        setAgentResult(updated);
        setReview({profile:updated.profile,assessments:updated.assessments,followups:updated.followups,
          changed_criteria:updated.changed_criteria,notice:updated.notice});
        setFollowupPlan(updated.followups);setChangedCriteria(updated.changed_criteria);
        setProfile(updated.profile);setConnection('Five agents reassessed updated facts');
        return true;
      }
      const updated=await reassessTrials(current,analysis.mode,analysis.trials.slice(0,8).map(t=>t.nct_id),{[factKey]:answer});
      setReview(updated);setFollowupPlan(updated.followups);setChangedCriteria(updated.changed_criteria);
      setProfile(updated.profile);setConnection('Shared facts reassessed');return true;
    }catch(err){setFollowupError(err instanceof Error?err.message:'Unable to apply this answer');return false;}
    finally{setAnswerBusy(false);}
  }

  useEffect(()=>{
    if(mode!=='live'){setRegistryStatus(null);setRegistryError('');return;}
    let active=true;
    setRegistryError('');
    checkLiveRegistry().then(data=>{if(active){setRegistryStatus(data);setConnection('Public registry reachable');}})
      .catch(err=>{if(active){setRegistryStatus(null);setRegistryError(err instanceof Error?err.message:'Registry unavailable');}});
    return ()=>{active=false;};
  },[mode]);
  useEffect(()=>{localStorage.setItem('ctm-saved',JSON.stringify(saved));},[saved]);
  useEffect(()=>{fetch((import.meta.env.VITE_API_BASE_URL||'http://localhost:8000')+'/health',{signal:AbortSignal.timeout(5000)}).then(r=>r.ok?setConnection('Backend connected'):setConnection('Offline-ready')).catch(()=>setConnection('Offline-ready'));},[]);
  const displayedAssessments=review?.assessments??analysis.assessments;
  const statusMap=useMemo(()=>new Map(displayedAssessments.map(a=>[a.nct_id,a])),[displayedAssessments]);
  const visible=analysis.trials.filter(t=>{
    const summary=statusMap.get(t.nct_id)?.summary;
    return (filter==='all'||(filter==='unresolved'&&summary==='needs_information')||(filter==='conflict'&&summary==='identified_conflict')||(filter==='unassessed'&&!summary)) && (!query||`${t.title} ${t.nct_id} ${t.conditions.join(' ')}`.toLowerCase().includes(query.toLowerCase()));
  });
  const selectTrial=(id:string)=>{setSelected(id);setPage('discover');};
  const selectedTrial=analysis.trials.find(t=>t.nct_id===selected);
  const selectedAssessment=statusMap.get(selected);
  const potentially=displayedAssessments.filter(a=>a.summary==='potential_match').length;
  const unresolved=displayedAssessments.filter(a=>a.summary==='needs_information'||a.summary==='clinical_review').length;
  const conflict=displayedAssessments.filter(a=>a.summary==='identified_conflict').length;
  const counts=[{label:'Retrieved',value:analysis.trials.length},{label:'Reviewed',value:displayedAssessments.length},{label:'Potential',value:potentially}];
  function toggleSaved(id:string){setSaved(prev=>prev.includes(id)?prev.filter(i=>i!==id):[...prev,id]);}
  function changeIntakeMode(next:'guided'|'quick'){
    setAgentResult(null);setAgentSettings(null);setReview(null);setFollowupPlan(null);
    setIntakeMode(next);setError('');setLiveSearched(false);
    setText('');setProfile(emptyPatient());setAnalysis(emptyAnalysis());setSelected('');
  }
  function selectedAgentSettings():AgentSettings{
    if(analysisDepth==='model'&&!teamToken.trim()){
      throw new Error('Enter your local team access token before selecting model-assisted analysis.');
    }
    return {depth:analysisDepth,token:analysisDepth==='model'?teamToken:''};
  }
  function finishAgentRun(result:AgentResult,settings:AgentSettings){
    if(result.mode!=='live')throw new Error('Only official live studies are supported in the dashboard.');
    requireOfficialStudies(result.trials);
    setAgentSettings(settings);setAgentResult(result);setProfile(result.profile);
    setAnalysis({mode:result.mode,profile:result.profile,trials:result.trials,assessments:result.assessments,
      timings_ms:{},disclaimer:result.notice});
    setSelected(result.trials[0]?.nct_id||'');
    setFollowupPlan(result.followups);setReview(null);setChangedCriteria([]);
    setLiveSearched(result.mode==='live');setConnection('Five-role matching workflow complete');
  }
  async function runGuidedSearch(submission:IntakeSubmission){
    setBusy(true);setError('');setAgentResult(null);setAgentSettings(null);setReview(null);setChangedCriteria([]);
    try{
      const built=await buildIntakeProfile(submission);
      const settings=selectedAgentSettings();
      const result=await runFiveAgents(built,mode,settings);
      finishAgentRun(result,settings);
    }catch(e){setError(e instanceof Error?e.message:'Guided intake failed');}
    finally{setBusy(false);}
  }
  async function runSearch(){
    if(!text.trim()){setError('Enter a fictional patient description containing a medical condition.');return;}
    setBusy(true);setError('');setAgentResult(null);setAgentSettings(null);
    setReview(null);setChangedCriteria([]);
    try{
      const parsed=await parseProfile(text,'live');
      if(!parsed.diagnosis)throw new Error('The condition could not be identified. Use Guided intake to enter the exact condition.');
      const settings=selectedAgentSettings();
      const result=await runFiveAgents(parsed,'live',settings);
      finishAgentRun(result,settings);
    }catch(e){setError(e instanceof Error?e.message:'Official registry search failed');}
    finally{setBusy(false);}
  }
  return <div className="app-shell"><Sidebar page={page} setPage={setPage} savedCount={saved.length}/><main className="main-content"><DashboardHeader connection={connection}/>
    <div className="safety-banner"><div><ShieldCheck size={17}/> Use fictional patient data only. This tool cannot establish eligibility.</div><a href="https://clinicaltrials.gov" target="_blank" rel="noopener noreferrer">Data source <ExternalLink size={13}/></a></div>
    {page==='discover'&&<><section className="intro-heading"><div><h2>Describe a patient</h2><p>We'll search for trials relevant to the condition you enter.</p></div></section>
      {mode==='live'&&<div className="registry-banner" role="status"><div><strong>ClinicalTrials.gov search</strong><p>Live study records; some results may be broad registries rather than disease-specific trials.</p></div><div className="registry-meta">{registryStatus?<><span className="registry-ok">Registry connected · API {registryStatus.api_version}</span><span>Registry updated {registryStatus.data_timestamp.replace('T',' ').slice(0,16)} UTC</span></>:registryError?<span className="registry-warning">{registryError}</span>:<span>Checking official registry connection…</span>}</div></div>}
      <AgentSetup depth={analysisDepth} onDepthChange={setAnalysisDepth}
        token={teamToken} onTokenChange={setTeamToken} disabled={busy||answerBusy}/>
      <div className="intake-method-switch" role="group" aria-label="Profile intake method">
        <div><strong>Patient details</strong></div>
        <div className="intake-method-buttons">
          <button className={intakeMode==='guided'?'active':''} onClick={()=>changeIntakeMode('guided')}>Guided intake</button>
          <button className={intakeMode==='quick'?'active':''} onClick={()=>changeIntakeMode('quick')}>Quick description</button>
        </div>
      </div>
      {intakeMode==='guided'?<GuidedIntake busy={busy} onSearch={runGuidedSearch}/>:<section className="patient-input panel">
        <div className="input-head"><div><label htmlFor="patient">Fictional patient description</label></div></div>
        <textarea id="patient" value={text} onChange={e=>setText(e.target.value)}
          rows={3} maxLength={3000} placeholder="Describe a fictional patient, including their condition, age, relevant medical history, and known test results."/>
      <div className="input-actions"><div className="extracted-tags"><span><Check size={13}/> {profile.age??'Unknown'} years</span><span><Check size={13}/> {profile.diagnosis||'Diagnosis needed'}</span>{profile.stage&&<span>{profile.stage}</span>}</div><button className="primary-button" onClick={runSearch} disabled={busy||!text.trim()}>{busy?<RefreshCw className="spin" size={16}/>:<Search size={17}/>} {busy?'Processing...':'Search ClinicalTrials.gov'} <ArrowRight size={15}/></button></div></section>}
      {error&&<div className="error-alert"><CircleAlert size={17}/>{error}<button onClick={()=>setError('')} aria-label="Dismiss"><X size={15}/></button></div>}
      {liveSearched&&analysis.trials.length===0&&<div className="live-action" role="status"><Info size={17}/><div><strong>No directly documented studies found for {analysis.profile.diagnosis}.</strong>
         <p>Some broader indexed results may exist, but we do not present them as confirmed disease matches. Try a recognized diagnosis or synonym.</p>
       </div></div>}
       <AgentWorkflow result={agentResult}/>
      {liveSearched&&<details className="analytics-toggle"><summary>View search statistics</summary>
       <div className="metrics-grid"><Metric icon={<Search size={19}/>} label="Trials retrieved" value={analysis.trials.length} sub="Candidate studies"/><Metric icon={<ClipboardList size={19}/>} label="Studies reviewed" value={displayedAssessments.length} sub="Partial criterion checks; not clinical screening"/><Metric icon={<Info size={19}/>} label="Need information" value={unresolved} sub="Unknown or review required"/><Metric icon={<CircleAlert size={19}/>} label="Eligibility conflicts" value={conflict} sub="Preliminary, not final" kind="warn"/></div>
      <div className="analytics-row"><div className="panel analytics-panel"><div className="panel-heading"><div><h3>Discovery funnel</h3><p>What the current pipeline processed</p></div><SlidersHorizontal size={17}/></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={counts} layout="vertical" margin={{top:5,right:24,left:0,bottom:0}}><CartesianGrid horizontal={false} stroke="#e8edf2"/><XAxis type="number" allowDecimals={false} tick={{fontSize:11,fill:'#718397'}} axisLine={false} tickLine={false}/><YAxis type="category" dataKey="label" width={74} tick={{fontSize:11,fill:'#526579'}} axisLine={false} tickLine={false}/><Tooltip contentStyle={{borderRadius:12,border:'1px solid #e3e9ee',fontSize:12}}/><Bar dataKey="value" barSize={17} radius={[0,6,6,0]}>{counts.map((_,i)=><Cell key={i} fill={['#355c8e','#3d988a','#88b9a8'][i]}/>)}</Bar></BarChart></ResponsiveContainer></div><div className="chart-caption">Current registry query counts, not a benchmark result</div></div>
      <div className="panel insights-panel"><div className="panel-heading"><div><h3>Assessment overview</h3><p>Conservative preliminary categories</p></div><Activity size={17}/></div><div className="insights-bars">{[{label:'Potential match',count:potentially,color:'#268a75'},{label:'Information needed',count:unresolved,color:'#d2a451'},{label:'Identified conflict',count:conflict,color:'#d47665'}].map(s=><div className="insight" key={s.label}><div className="insight-meta"><span>{s.label}</span><strong>{s.count}</strong></div><div className="track"><div style={{width:`${displayedAssessments.length?s.count/displayedAssessments.length*100:0}%`,background:s.color}}/></div></div>)}</div><div className="chart-caption"><Info size={13}/> Relevance is not eligibility. Unknown is not a pass.</div></div></div>
      </details>}
       <TrialFollowups independentReviewCount={displayedAssessments.filter(a=>a.skeptic.length>0).length}
         clarificationModelUsed={agentResult?.trace.some(t=>t.agent==='clarification'&&t.execution==='model')??false}
         plan={followupPlan} loading={followupBusy} submitting={answerBusy} error={followupError}
        answers={review?.profile.followup_answers||{}} changed={changedCriteria}
        onSelectTrial={selectTrial} onAnswer={answerFollowup}/>
      <div className="results-head"><div><h2>Study results <span>({visible.length})</span></h2></div><div className="result-tools"><div className="search-small"><Search size={15}/><input placeholder="Filter studies..." value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="filter-box"><Filter size={14}/><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All statuses</option><option value="unresolved">Needs info</option><option value="conflict">Conflicts</option><option value="unassessed">Not assessed</option></select></div></div></div>
      <div className="results-grid"><div className="trial-list">{visible.length?visible.map(t=><TrialCard key={t.nct_id} trial={t} assessment={statusMap.get(t.nct_id)} selected={selected===t.nct_id} saved={saved.includes(t.nct_id)} onSelect={()=>setSelected(t.nct_id)} onSave={()=>toggleSaved(t.nct_id)}/>):<div className="large-empty"><Search size={24}/><p>{liveSearched&&!analysis.trials.length?'No studies with documented condition links found.':'No studies match your filters.'}</p></div>}</div><div className="panel detail-container"><EligibilityDetail trial={selectedTrial} assessment={selectedAssessment}/></div></div>
      
    </>}
    {page==='saved'&&<SavedView trials={analysis.trials} assessments={displayedAssessments} saved={saved} setSaved={setSaved} onSelect={selectTrial}/>}
    {page==='research'&&<ResearchLab/>}
    <footer className="footer"><span>ClinicalTrial Matcher · Hackaroo 2026</span><span>Built for transparent research navigation, not clinical decisions.</span></footer>
  </main></div>
}
