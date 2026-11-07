import {useEffect, useMemo, useState} from 'react';
import {AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, ClipboardCheck, HelpCircle, Loader2, ShieldCheck} from 'lucide-react';
import type {IntakeAnswer, IntakeQuestion, IntakeSubmission} from '../types';
import {fetchIntakeQuestions} from '../lib/api';

const STEPS = [
  {id:'basics',name:'Condition & basics',description:'Build a starting point without guessing.'},
  {id:'history',name:'Treatments & tests',description:'Tell us what is known about the medical history.'},
  {id:'access',name:'Location & story',description:'Add access preferences and any optional context.'},
  {id:'review',name:'Review profile',description:'Check the information before discovering studies.'}
] as const;
const STATUS_OPTIONS: {value: IntakeAnswer['state']|''; label:string}[] = [
  {value:'',label:'Not answered'}, {value:'answered',label:'I know the answer'},
  {value:'unknown',label:"I don't know"},{value:'pending',label:'Result pending'},
  {value:'not_tested',label:'Not tested'},{value:'not_applicable',label:'Not applicable'},
  {value:'declined',label:'Prefer not to answer'}
];
const TEST_RESULT_KEYS = new Set(['egfr_result','alk_result','cftr_result','her2_result','sickle_genotype']);
const EXAMPLES = [
  {label:'Lung cancer',value:'non-small cell lung cancer'},
  {label:'Sickle cell',value:'sickle cell disease'},
  {label:'Cystic fibrosis',value:'cystic fibrosis'}
];
function normalizedCondition(raw:string) {
  const condition=raw.trim().toLowerCase().replace(/\s+/g,' ');
  return condition==='nsclc'?'non-small cell lung cancer':condition==='sickle cell anemia'?'sickle cell disease':condition;
}
function statusLabel(answer: IntakeAnswer|undefined) {
  if (!answer) return 'Not provided';
  return answer.state==='answered' ? answer.value || 'Incomplete' : STATUS_OPTIONS.find(x=>x.value===answer.state)?.label || answer.state;
}

interface Props {
  onSearch: (submission: IntakeSubmission)=>Promise<void>;
  busy: boolean;
  mode: 'replay'|'live';
}

export default function GuidedIntake({onSearch,busy,mode}:Props) {
  const [questions,setQuestions]=useState<IntakeQuestion[]>([]);
  const [loadError,setLoadError]=useState('');
  const [answers,setAnswers]=useState<Record<string,IntakeAnswer>>({});
  const [narrative,setNarrative]=useState('');
  const [step,setStep]=useState(0);
  const condition=normalizedCondition(answers.condition?.value || '');

  useEffect(()=>{
    let alive=true;
    fetchIntakeQuestions().then(data=>{if(alive) {setQuestions(data.questions);setLoadError('');}})
      .catch(e=>{if(alive)setLoadError(e instanceof Error?e.message:'Question bank unavailable')});
    return ()=>{alive=false};
  },[]);

  const applicable=useMemo(()=>questions.filter(q=>!q.conditions.length||q.conditions.includes(condition)),[questions,condition]);
  const current=applicable.filter(q=>q.section===STEPS[step].id);
  const provided=Object.values(answers).filter(a=>a.state==='answered' && !!a.value?.trim()).length;
  const unanswered=applicable.filter(q=>q.id!=='condition' && (!answers[q.id] || answers[q.id].state!=='answered')).length;
  const validCondition=answers.condition?.state==='answered' && condition.length>=3;
  const invalidAnswer=Object.entries(answers).some(([id,ans])=>applicable.some(q=>q.id===id) && ans.state==='answered' && !ans.value?.trim());

  function setCondition(value:string) {
    const normalized=normalizedCondition(value);
    setAnswers(old=>{
      const next:Record<string,IntakeAnswer>={condition:{state:'answered',value}};
      for (const [id,answer] of Object.entries(old)) {
        const q=questions.find(q=>q.id===id);
        if (id!=='condition' && q && (!q.conditions.length||q.conditions.includes(normalized)))next[id]=answer;
      }
      return next;
    });
  }
  function setStatus(id:string,state: IntakeAnswer['state']|'') {
    setAnswers(old=>{
      const next={...old};
      if(!state){delete next[id];return next;}
      next[id]={state,value:state==='answered'?(old[id]?.value||''):null};
      return next;
    });
  }
  function setValue(id:string,value:string){setAnswers(old=>({...old,[id]:{state:'answered',value}}));}

  function renderQuestion(question:IntakeQuestion) {
    const answer=answers[question.id];
    const isCondition=question.id==='condition';
    return <div className="intake-question" key={question.id}>
      <label htmlFor={'intake-'+question.id}>{question.label}{question.required_for_search&&<span className="required-asterisk"> *</span>}</label>
      <div className="intake-help"><HelpCircle size={13}/>{question.help}</div>
      {isCondition?<>
        <input id="intake-condition" value={answer?.value||''} maxLength={120} placeholder={question.placeholder}
          onChange={e=>setCondition(e.target.value)} />
        <div className="intake-suggestions">{EXAMPLES.map(ex=><button type="button" key={ex.label}
          className={condition===ex.value?'chosen':''} onClick={()=>setCondition(ex.value)}>{ex.label}</button>)}</div>
      </>:<>
        <select aria-label={`${question.label} — answer status`} value={answer?.state||''} onChange={e=>setStatus(question.id,e.target.value as IntakeAnswer['state']|'')}>
          {STATUS_OPTIONS.filter(x=>TEST_RESULT_KEYS.has(question.id)||!['pending','not_tested'].includes(x.value)).map(x=><option value={x.value} key={x.value}>{x.label}</option>)}
        </select>
        {answer?.state==='answered'&&(question.input_type==='select'
          ? <select id={'intake-'+question.id} value={answer.value||''} onChange={e=>setValue(question.id,e.target.value)}>
              <option value="">Select an answer</option>{question.options.map(o=><option value={o} key={o}>{o}</option>)}
            </select>
          : <input id={'intake-'+question.id} value={answer.value||''} maxLength={250}
              type={question.input_type==='number'?'number':'text'} min={question.input_type==='number'?0:undefined}
              max={question.input_type==='number'?120:undefined}
              placeholder={question.placeholder} onChange={e=>setValue(question.id,e.target.value)}/>
        )}
      </>}
    </div>;
  }

  async function submit() {
    if (!validCondition || invalidAnswer || busy) return;
    await onSearch({answers, narrative, synthetic:true});
  }

  return <section className="guided-intake panel">
    <div className="guided-intake-header">
      <div><div className="section-eyebrow"><ClipboardCheck size={15}/> GUIDED PATIENT INTAKE</div><h3>Build a clearer patient profile</h3>
        <p>Synthetic patients only. You can skip unknown information; it will never count as a negative test or a clinical clearance.</p></div>
      <span className="intake-version">MVP 1.5-A</span>
    </div>
    <div className="intake-steps" aria-label="Intake progress">{STEPS.map((item,i)=><button type="button" key={item.id}
      className={step===i?'active':i<step?'complete':''} disabled={i>step+1||i>0&&!validCondition}
      onClick={()=>setStep(i)}><span>{i<step?<CheckCircle2 size={15}/>:i+1}</span>{item.name}</button>)}</div>
    <div className="intake-step-head"><h4>{STEPS[step].name}</h4><p>{STEPS[step].description}</p></div>
    {loadError&&<div className="intake-error"><AlertCircle size={16}/> Cannot load guided questions from the backend: {loadError}</div>}
    {!loadError && questions.length===0&&<p className="intake-help"><Loader2 size={14}/> Loading question bank...</p>}
    {questions.length>0&&<>
      {step<3?<>
        <div className="intake-question-grid">{current.map(renderQuestion)}
          {step===2&&<div className="intake-question intake-narrative">
            <label htmlFor="intake-story">Optional patient story</label>
            <div className="intake-help">Additional context is retained for human review. It does not silently overwrite answers you confirmed above.</div>
            <textarea id="intake-story" rows={3} maxLength={1500} value={narrative} onChange={e=>setNarrative(e.target.value)}
              placeholder="Optional fictional context: diagnosis history, questions or preferences..."/>
          </div>}
        </div>
      </>:<>
        <div className="intake-review-banner"><ShieldCheck size={18}/><div><strong>Review your synthetic profile</strong><p>Structured answers take precedence over your free-text story. Unanswered questions remain unresolved.</p></div></div>
        <div className="intake-review-grid">{applicable.map(q=><div key={q.id} className="intake-review-row"><span>{q.label}</span>
          <strong>{statusLabel(answers[q.id])}</strong></div>)}</div>
        {narrative.trim()&&<div className="intake-story-review"><b>Optional story:</b> {narrative}</div>}
        <p className="intake-summary">{provided} answered facts · {unanswered} unanswered or uncertain fields. A condition is sufficient to begin discovery.</p>
      </>}
      <div className="intake-footer"><span>Research use only · No real medical records</span>
        <div className="intake-controls">
          {step>0&&<button type="button" className="secondary-button" disabled={busy} onClick={()=>setStep(x=>x-1)}><ArrowLeft size={15}/> Back</button>}
          {step<3?<button type="button" className="primary-button" disabled={!validCondition||!questions.length||invalidAnswer}
            onClick={()=>setStep(x=>x+1)}>Continue <ArrowRight size={15}/></button>
          :<button type="button" className="primary-button" disabled={busy||!validCondition||invalidAnswer}
            onClick={()=>void submit()}>{busy?<Loader2 size={16} className="spin"/>:<ArrowRight size={16}/>}
              {mode==='replay'?'Discover fictional trials':'Search real trial registry'}</button>}
        </div>
      </div>
    </>}
  </section>;
}
