import {useEffect,useMemo,useState} from 'react';
import {Activity,ArrowRight,BarChart3,Bookmark,BookOpen,Check,CheckCircle2,ChevronDown,ChevronRight,CircleAlert,ClipboardList,Download,ExternalLink,Filter,FlaskConical,HeartPulse,Info,MapPin,Microscope,RefreshCw,Search,ShieldCheck,SlidersHorizontal,Sparkles,X} from 'lucide-react';
import {Bar,BarChart,CartesianGrid,Cell,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';
import type {Analysis,Mode,Page,PatientProfile,Status,Summary,Trial,TrialAssessment} from './types';
import {offlineAnalysis,sampleDescription,syntheticPatient} from './data/fixture';
import {analyze,parseProfile,searchTrials} from './lib/api';

const STATUS_LABEL:Record<Summary,string>={potential_match:'Potential match',needs_information:'Needs more information',identified_conflict:'Eligibility conflict',clinical_review:'Clinical review required'};
const SANDBOX_EXAMPLES=[
  {name:'Lung cancer',description:sampleDescription},
  {name:'Sickle cell',description:'29-year-old patient with sickle cell disease. Lives in Chicago, Illinois. Previous treatments are unknown.'},
  {name:'Cystic fibrosis',description:'16-year-old patient with cystic fibrosis. CFTR genetic variant status is unknown. Lives in Boston, Massachusetts.'}
];
const CRITERION_LABEL:Record<Status,string>={met:'Met / present',not_met:'Not met / absent',unknown:'Unknown',clinical_review:'Clinical review'};
function slug(s:string){return s.toLowerCase().replace(/_/g,'-')}
function getStorage():string[]{try{return JSON.parse(localStorage.getItem('ctm-saved')||'[]') as string[]}catch{return []}}

function DashboardHeader({mode,connection}:{mode:Mode;connection:string}){
  return <div className="top-header">
    <div><div className="crumb">RESEARCH PLATFORM <ChevronRight size={12}/> CLINICAL TRIAL DISCOVERY</div><h1>Trial discovery, with evidence.</h1><p>From a patient story to traceable research opportunities.</p></div>
    <div className="header-side"><span className="live-dot"/><span>{mode==='replay'?'Synthetic replay':'Live trial data'}</span><span className="header-sep"/> <span className="status-sub">{connection}</span></div>
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
  const items=[{id:'discover',label:'Discover trials',icon:<Search size={18}/>},{id:'saved',label:'Saved & compare',icon:<Bookmark size={18}/>},{id:'research',label:'Research lab',icon:<BarChart3 size={18}/>}];
  return <aside className="sidebar">
    <div className="brand"><div className="brand-icon"><HeartPulse size={24}/></div><div className="brand-copy"><strong>ClinicalTrial</strong><span>Matcher<span className="brand-dot">.</span></span></div></div>
    <div className="nav-label">WORKSPACE</div>
    <nav>{items.map(it=><button key={it.id} className={'nav-link '+(page===it.id?'active':'')} onClick={()=>setPage(it.id as Page)}>{it.icon}<span>{it.label}</span>{it.id==='saved'&&savedCount>0&&<span className="nav-count">{savedCount}</span>}</button>)}</nav>
    <div className="sidebar-spacer"/>
    <div className="sidebar-card"><div className="sidebar-card-head"><ShieldCheck size={16}/> EVIDENCE-FIRST AI</div><p>Every assessment should point to original trial criteria. Unknown is never assumed eligible.</p><div className="sidebar-signal"><span className="live-dot"/> Research prototype</div></div>
    <div className="sidebar-footer">HACKAROO 2026 <span>•</span> v0.1</div>
  </aside>;
}
function TrialCard({trial,assessment,selected,saved,onSelect,onSave}:{trial:Trial;assessment?:TrialAssessment;selected:boolean;saved:boolean;onSelect:()=>void;onSave:()=>void}){
  return <div className={'trial-card '+(selected?'selected':'')}>
    <div className="trial-card-top"><span className="trial-id">{trial.nct_id}</span><button className={'icon-button save-icon '+(saved?'saved':'')} title={saved?'Remove from saved':'Save trial'} onClick={onSave}><Bookmark size={16} fill={saved?'currentColor':'none'}/></button></div>
    <button className="trial-title-button" onClick={onSelect}>{trial.title}<ChevronRight size={17}/></button>
    <div className="trial-tags"><span className="pill"><span className="small-dot"/>{trial.status.replaceAll('_',' ')}</span><span className="pill">{trial.phase.join(', ').replaceAll('_',' ')||'Phase unspecified'}</span></div>
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
    <div className="detail-meta"><span>{trial.nct_id}</span><span>•</span><span>{trial.status.replaceAll('_',' ')}</span></div>
    <div className="detail-summary"><SummaryBadge summary={assessment?.summary}/><p>{assessment?.summary==='identified_conflict'?'A requirement conflicts with the provided synthetic profile.':assessment?.summary==='potential_match'?'No conflicts detected in this preliminary analysis; screening is still required.':assessment?'Important information remains unresolved. Do not treat this as confirmed eligibility.':'This study has not been assessed. Relevance is not eligibility.'}</p></div>
    {assessment?<>
      <div className="mini-stats"><span><b>{counts.inclusion}</b> Inclusion</span><span><b>{counts.exclusion}</b> Exclusion</span><span><b>{counts.unknown}</b> Unresolved</span></div>
      <div className="subsection-label">CRITERION-BY-CRITERION ANALYSIS <span>{pairs.length} identified</span></div>
      <div className="criterion-list">{pairs.map(({c,a,s})=><div className="criterion" key={c.id}>
        <button className="criterion-header" onClick={()=>setExpanded(expanded===c.id?null:c.id)} aria-expanded={expanded===c.id}>
          <div className="criterion-names"><span className="criterion-id">{c.id}</span><span className="criterion-heading">{c.text}</span></div><div className="criterion-status">{a&&<CritBadge status={a.status} kind={c.kind}/>}<ChevronDown size={14} className={expanded===c.id?'rotate':''}/></div>
        </button>
        {expanded===c.id&&<div className="criterion-body"><div className="evidence-label">EXACT TRIAL REQUIREMENT</div><blockquote>“{c.source_text}”</blockquote><div className="evidence-label">ASSESSMENT</div><p>{a?.explanation||'Not assessed'}</p><div className="evidence-label">PATIENT EVIDENCE</div><p>{a?.patient_evidence?.length?a.patient_evidence.map(v=>`“${v}”`).join(' · '):'No verified patient evidence recorded.'}</p>{a?.question_for_doctor&&<div className="question"><Info size={14}/>{a.question_for_doctor}</div>}<div className="skeptic-row"><ShieldCheck size={14}/> Independent review: {s?.disagreement?'Disagreement flagged':s?'No disagreement recorded':'Not yet available'}</div></div>}
      </div>)}</div>
      <div className="review-footnote"><ShieldCheck size={16}/><span>{assessment.provenance==='synthetic_replay'?'Illustrative, pre-authored independent review. Not a live model measurement.':'Independent model review performed; human clinical screening still required.'}</span></div>
    </>:<div className="unassessed-criteria"><div className="empty-assessment"><Info size={17}/><span>No eligibility or skeptic assessment has been performed for this profile. Trial relevance alone does not imply eligibility. Authorized AI assessment requires optional free-tier model setup.</span></div><div className="evidence-label">ORIGINAL STUDY REQUIREMENTS — NOT EVALUATED</div><pre>{trial.eligibility_text || 'Eligibility criteria are not available in this trial record.'}</pre></div>}
    {trial.url&&<a className="official-link" href={trial.url} target="_blank" rel="noopener noreferrer">View original ClinicalTrials.gov study <ExternalLink size={14}/></a>}
    <div className="disclaimer-line">Research/navigation only • Not clinical advice • Study team determines eligibility</div>
  </div>;
}
function ResearchLab(){
  const planned=[{key:'nDCG@10',name:'Retrieval ranking'},{key:'Exclusion recall',name:'Eligibility safety'},{key:'Skeptic corrections',name:'Independent review'},{key:'Attack success',name:'Prompt injection'}];
  return <div className="research-content"><div className="section-eyebrow"><Microscope size={14}/> REPRODUCIBLE RESEARCH</div><h2>Evaluation laboratory</h2><p className="lead">Measurements will appear only after the corresponding benchmark experiments have been run. Synthetic replay results are never treated as research findings.</p>
    <div className="metrics-grid">{planned.map(p=><Metric key={p.key} icon={<Activity size={18}/>} label={p.key} value="—" sub="Not measured"/>)}</div>
    <div className="research-grid"><div className="panel paper"><div className="panel-heading"><h3>Retrieval benchmark</h3><span className="subtle-tag">PLANNED</span></div><p>Compare BM25 against semantic/hybrid ranking on the historical TREC Clinical Trials snapshot, using the corresponding relevance judgments.</p><div className="research-placeholder"><BarChart3 size={28}/><strong>Awaiting measured benchmark results</strong><span>nDCG@10 • Precision@K • eligible-trial Recall@K</span></div></div><div className="panel paper"><div className="panel-heading"><h3>Safety & verification</h3><span className="subtle-tag">PLANNED</span></div><p>Evaluate criterion accuracy, missed exclusions, skeptical agent corrections, false-positive findings, and malicious retrieved text.</p><div className="research-placeholder"><ShieldCheck size={28}/><strong>Awaiting labeled test runs</strong><span>Confusion matrix • disagreements • attack outcomes</span></div></div></div>
    <div className="research-method"><h3>Evidence standards</h3><div className="method-cards"><div><strong>01 / Historical corpus</strong><p>Never substitute today's public registry for the original TREC benchmark snapshot.</p></div><div><strong>02 / Labeled cases</strong><p>Separate clinician-unverified synthetic criterion labels from genuine clinical expert annotations.</p></div><div><strong>03 / Exact provenance</strong><p>Record dataset version, model, prompt, sample size, response time and failures per run.</p></div></div></div>
  </div>;
}
function SavedView({trials,assessments,saved,setSaved,onSelect}:{trials:Trial[];assessments:TrialAssessment[];saved:string[];setSaved:(x:string[])=>void;onSelect:(x:string)=>void}){
  const matches=trials.filter(t=>saved.includes(t.nct_id));
  return <div className="saved-view"><div className="section-eyebrow"><Bookmark size={14}/> PATIENT WORKSPACE</div><h2>Saved trials & physician handoff</h2><p className="lead">Keep synthetic demonstration studies together, compare eligibility findings, and prepare questions for a clinical discussion.</p>
    <div className="saved-toolbar"><div><b>{matches.length}</b> selected studies in this session</div><button className="primary-button" disabled={matches.length===0} onClick={()=>window.print()}><Download size={16}/> Print / Save report as PDF</button></div>
    {!matches.length?<div className="large-empty"><Bookmark size={29}/><h3>No saved studies</h3><p>Choose the bookmark icon on a trial to include it in your comparison and physician handoff summary.</p></div>:<div className="saved-list">{matches.map(t=>{const a=assessments.find(x=>x.nct_id===t.nct_id);return <div className="saved-row" key={t.nct_id}><div><span className="trial-id">{t.nct_id}</span><h3>{t.title}</h3><SummaryBadge summary={a?.summary}/></div><div className="saved-actions"><button onClick={()=>onSelect(t.nct_id)} className="secondary-button">Inspect <ArrowRight size={14}/></button><button className="icon-button" onClick={()=>setSaved(saved.filter(id=>id!==t.nct_id))}><X size={16}/></button></div></div>})}</div>}
    {matches.length>0&&<section className="print-report"><h2>Physician discussion brief — synthetic research example</h2><p>This report is a research/navigation aid. No eligibility or treatment advice is provided.</p>{matches.map(t=>{const a=assessments.find(x=>x.nct_id===t.nct_id);return <div key={t.nct_id}><h3>{t.nct_id}: {t.title}</h3><p>Preliminary status: {a?STATUS_LABEL[a.summary]:'Not assessed'}</p><p>Official source: {t.url||'Synthetic demonstration study, no official source'}</p>{a?.assessments.filter(x=>x.question_for_doctor).map(x=><p key={x.criterion_id}>Question ({x.criterion_id}): {x.question_for_doctor}</p>)}</div>})}</section>}
    <div className="notice"><Info size={16}/><p>Saved trial identifiers are stored only in this browser for demonstration. They are not synchronized to clinicians and no notification is sent.</p></div>
  </div>;
}

export default function App(){
  const [page,setPage]=useState<Page>('discover');
  const [mode,setMode]=useState<Mode>('replay');
  const [text,setText]=useState(sampleDescription);
  const [profile,setProfile]=useState<PatientProfile>(syntheticPatient());
  const [analysis,setAnalysis]=useState<Analysis>(offlineAnalysis);
  const [selected,setSelected]=useState('DEMO-001');
  const [saved,setSaved]=useState<string[]>(getStorage);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [connection,setConnection]=useState('Offline-ready');
  const [filter,setFilter]=useState('all');
  const [query,setQuery]=useState('');
  const [liveSearched,setLiveSearched]=useState(false);
  const [liveToken,setLiveToken]=useState('');
  useEffect(()=>{localStorage.setItem('ctm-saved',JSON.stringify(saved));},[saved]);
  useEffect(()=>{fetch((import.meta.env.VITE_API_BASE_URL||'http://localhost:8000')+'/health',{signal:AbortSignal.timeout(5000)}).then(r=>r.ok?setConnection('Backend connected'):setConnection('Offline-ready')).catch(()=>setConnection('Offline-ready'));},[]);
  const statusMap=useMemo(()=>new Map(analysis.assessments.map(a=>[a.nct_id,a])),[analysis]);
  const visible=analysis.trials.filter(t=>{
    const summary=statusMap.get(t.nct_id)?.summary;
    return (filter==='all'||(filter==='unresolved'&&summary==='needs_information')||(filter==='conflict'&&summary==='identified_conflict')||(filter==='unassessed'&&!summary)) && (!query||`${t.title} ${t.nct_id} ${t.conditions.join(' ')}`.toLowerCase().includes(query.toLowerCase()));
  });
  const selectTrial=(id:string)=>{setSelected(id);setPage('discover');};
  const selectedTrial=analysis.trials.find(t=>t.nct_id===selected);
  const selectedAssessment=statusMap.get(selected);
  const potentially=analysis.assessments.filter(a=>a.summary==='potential_match').length;
  const unresolved=analysis.assessments.filter(a=>a.summary==='needs_information'||a.summary==='clinical_review').length;
  const conflict=analysis.assessments.filter(a=>a.summary==='identified_conflict').length;
  const counts=[{label:'Retrieved',value:analysis.trials.length},{label:'Assessed',value:analysis.assessments.length},{label:'Potential',value:potentially}];
  function toggleSaved(id:string){setSaved(prev=>prev.includes(id)?prev.filter(i=>i!==id):[...prev,id]);}
  function changeMode(next:Mode){setMode(next);setError('');setText(sampleDescription);setProfile(syntheticPatient());setAnalysis(next==='replay'?offlineAnalysis:{...offlineAnalysis,mode:'live',trials:[],assessments:[]});setSelected(next==='replay'?'DEMO-001':'');setLiveSearched(false);}
  async function runSearch(){
    setBusy(true);setError('');
    try{
      const parsed=await parseProfile(text,mode,liveToken||undefined);setProfile(parsed);
      if(mode==='replay'){
        const next=await analyze(parsed,'replay');setAnalysis(next);setSelected(next.trials[0]?.nct_id||'');setConnection('Replay via backend');
      }else{
        const searched=await searchTrials(parsed,'live');
        setAnalysis({mode:'live',profile:parsed,trials:searched.trials,assessments:[],timings_ms:{},disclaimer:'Live public study discovery; no eligibility assessment has been performed.'});
        setSelected(searched.trials[0]?.nct_id||'');setLiveSearched(true);setConnection('Live registry connected');
      }
    }catch(e){
      if(mode==='replay' && text.trim()===sampleDescription.trim()){setAnalysis(offlineAnalysis);setConnection('Offline replay');setError('Backend unavailable — showing the original fixed synthetic example.');}
      else if(mode==='replay'){setError('Interactive sandbox requires the FastAPI backend. Check http://localhost:8000/health, then try again.');}
      else{setError(e instanceof Error?e.message:'Request failed');}
    }finally{setBusy(false);}
  }
  async function runLiveAnalysis(){setBusy(true);setError('');try{const result=await analyze(profile,'live',liveToken||undefined);setAnalysis(result);setSelected(result.trials[0]?.nct_id||'');setConnection('Live AI analysis complete');}catch(e){setError(e instanceof Error?e.message:'Analysis unavailable');}finally{setBusy(false);}}
  return <div className="app-shell"><Sidebar page={page} setPage={setPage} savedCount={saved.length}/><main className="main-content"><DashboardHeader mode={mode} connection={connection}/>
    <div className="safety-banner"><div><ShieldCheck size={17}/><strong>Research demonstration</strong><span>•</span> Synthetic patient data only. No medical advice or eligibility determination.</div><a href="https://clinicaltrials.gov" target="_blank" rel="noopener noreferrer">Data source <ExternalLink size={13}/></a></div>
    {page==='discover'&&<><section className="intro-heading"><div><div className="section-eyebrow"><Sparkles size={15}/> AI-ASSISTED DISCOVERY</div><h2>Start with a patient story.</h2><p>We'll find relevant studies and show exactly what is known, uncertain, or conflicting.</p></div><div className="mode-switch"><button className={mode==='replay'?'chosen':''} onClick={()=>changeMode('replay')}>Interactive sandbox</button><button className={mode==='live'?'chosen':''} onClick={()=>changeMode('live')}>Live registry</button></div></section>
      <section className="patient-input panel"><div className="input-head"><div><label htmlFor="patient">SYNTHETIC PATIENT DESCRIPTION</label><p>{mode==='replay'?'Edit a fictional profile or select a scenario below. The original example has pre-authored assessments; custom profiles show trial discovery only.':'Public registry search. Use synthetic details only; AI assessment requires opt-in server configuration.'}</p></div><span className="synthetic-tag">SYNTHETIC ONLY</span></div><textarea id="patient" value={text} onChange={e=>setText(e.target.value)} rows={3} maxLength={3000}/>{mode==='replay'&&<div className="scenario-examples"><span>Try a fictional example:</span>{SANDBOX_EXAMPLES.map(example=><button key={example.name} type="button" disabled={busy} className={text===example.description?'active':''} onClick={()=>{setText(example.description);setError('');}}>{example.name}</button>)}</div>}{mode==='live'&&<div className="live-token-control"><label htmlFor="team-token">TEAM AI ACCESS TOKEN (OPTIONAL FOR PUBLIC TRIAL SEARCH)</label><input id="team-token" type="password" autoComplete="off" placeholder="Required for authorized live AI profiling and eligibility analysis" value={liveToken} onChange={e=>setLiveToken(e.target.value)}/><span>Kept only in this browser session's memory. Never place API keys here.</span></div>}
      <div className="input-actions"><div className="extracted-tags"><span><Check size={13}/> {profile.age??'Unknown'} years</span><span><Check size={13}/> {profile.diagnosis||'Diagnosis needed'}</span>{profile.stage&&<span>{profile.stage}</span>}</div><button className="primary-button" onClick={runSearch} disabled={busy}>{busy?<RefreshCw className="spin" size={16}/>:<Search size={17}/>} {busy?'Processing...':mode==='replay'?'Explore synthetic trials':'Search ClinicalTrials.gov'} <ArrowRight size={15}/></button></div></section>
      {error&&<div className="error-alert"><CircleAlert size={17}/>{error}<button onClick={()=>setError('')} aria-label="Dismiss"><X size={15}/></button></div>}
      {mode==='live'&&liveSearched&&<div className="live-action"><Info size={17}/><div><strong>Live trial discovery completed.</strong><p>Matching studies are not eligibility assessments. AI analysis is optional and disabled on publicly deployed backends unless explicitly enabled.</p></div><button className="secondary-button" disabled={busy} onClick={runLiveAnalysis}>Run eligibility + skeptic</button></div>}
      <div className="metrics-grid"><Metric icon={<Search size={19}/>} label="Trials retrieved" value={analysis.trials.length} sub="Candidate studies"/><Metric icon={<ClipboardList size={19}/>} label="Full assessments" value={analysis.assessments.length} sub="Criterion-level evaluations"/><Metric icon={<Info size={19}/>} label="Need information" value={unresolved} sub="Unknown or review required"/><Metric icon={<CircleAlert size={19}/>} label="Eligibility conflicts" value={conflict} sub="Preliminary, not final" kind="warn"/></div>
      <div className="analytics-row"><div className="panel analytics-panel"><div className="panel-heading"><div><h3>Discovery funnel</h3><p>What the current pipeline processed</p></div><SlidersHorizontal size={17}/></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={counts} layout="vertical" margin={{top:5,right:24,left:0,bottom:0}}><CartesianGrid horizontal={false} stroke="#e8edf2"/><XAxis type="number" allowDecimals={false} tick={{fontSize:11,fill:'#718397'}} axisLine={false} tickLine={false}/><YAxis type="category" dataKey="label" width={74} tick={{fontSize:11,fill:'#526579'}} axisLine={false} tickLine={false}/><Tooltip contentStyle={{borderRadius:12,border:'1px solid #e3e9ee',fontSize:12}}/><Bar dataKey="value" barSize={17} radius={[0,6,6,0]}>{counts.map((_,i)=><Cell key={i} fill={['#355c8e','#3d988a','#88b9a8'][i]}/>)}</Bar></BarChart></ResponsiveContainer></div><div className="chart-caption">{mode==='replay'?'Fictional studies — illustrative counts':'Current live query counts, not a benchmark result'}</div></div>
      <div className="panel insights-panel"><div className="panel-heading"><div><h3>Assessment overview</h3><p>Conservative preliminary categories</p></div><Activity size={17}/></div><div className="insights-bars">{[{label:'Potential match',count:potentially,color:'#268a75'},{label:'Information needed',count:unresolved,color:'#d2a451'},{label:'Identified conflict',count:conflict,color:'#d47665'}].map(s=><div className="insight" key={s.label}><div className="insight-meta"><span>{s.label}</span><strong>{s.count}</strong></div><div className="track"><div style={{width:`${analysis.assessments.length?s.count/analysis.assessments.length*100:0}%`,background:s.color}}/></div></div>)}</div><div className="chart-caption"><Info size={13}/> Relevance is not eligibility. Unknown is not a pass.</div></div></div>
      <div className="results-head"><div><div className="section-eyebrow"><BookOpen size={14}/> EXPLORE RESULTS</div><h2>Clinical trial matches <span>({visible.length})</span></h2></div><div className="result-tools"><div className="search-small"><Search size={15}/><input placeholder="Filter studies..." value={query} onChange={e=>setQuery(e.target.value)}/></div><div className="filter-box"><Filter size={14}/><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All statuses</option><option value="unresolved">Needs info</option><option value="conflict">Conflicts</option><option value="unassessed">Not assessed</option></select></div></div></div>
      <div className="results-grid"><div className="trial-list">{visible.length?visible.map(t=><TrialCard key={t.nct_id} trial={t} assessment={statusMap.get(t.nct_id)} selected={selected===t.nct_id} saved={saved.includes(t.nct_id)} onSelect={()=>setSelected(t.nct_id)} onSave={()=>toggleSaved(t.nct_id)}/>):<div className="large-empty"><Search size={24}/><p>No studies match the current filter.</p></div>}</div><div className="panel detail-container"><EligibilityDetail trial={selectedTrial} assessment={selectedAssessment}/></div></div>
      <div className="source-note"><Info size={15}/>{mode==='replay'?'Interactive sandbox: fictional trial data. Only the exact original example includes pre-authored educational judgments; edited profiles receive no AI eligibility or skeptic verdict.':'Live mode: Studies are retrieved from ClinicalTrials.gov. AI conclusions (when enabled) are preliminary and unvalidated.'}</div>
    </>}
    {page==='saved'&&<SavedView trials={analysis.trials} assessments={analysis.assessments} saved={saved} setSaved={setSaved} onSelect={selectTrial}/>}
    {page==='research'&&<ResearchLab/>}
    <footer className="footer"><span>ClinicalTrial Matcher · Hackaroo 2026</span><span>Built for transparent research navigation, not clinical decisions.</span></footer>
  </main></div>
}
