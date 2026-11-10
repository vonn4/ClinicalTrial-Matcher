import {useEffect,useState} from 'react';
import {ArrowRight, ChevronDown, FileText, Info, Loader2, Pencil, ShieldCheck, CheckCircle2} from 'lucide-react';
import type {CriterionDelta,FollowupPlan,FollowupQuestion,IntakeAnswer,IntakeAnswerState} from '../types';

interface Props {
  plan: FollowupPlan | null;
  loading: boolean;
  submitting: boolean;
  error: string;
  answers: Record<string,IntakeAnswer>;
  changed: CriterionDelta[];
  onSelectTrial: (id: string) => void;
  onAnswer: (factKey:string,answer:IntakeAnswer)=>Promise<boolean>;
  independentReviewCount?:number;
  clarificationModelUsed?:boolean;
}

const STATE_NOTE: Record<string,string> = {
  missing:'Not provided in the profile',
  unknown:'Marked unknown in intake',
  pending:'Test result pending — not negative',
  not_tested:'Not tested — not negative',
  not_applicable:'Marked not applicable; study team should review',
  declined:'Patient chose not to answer',
};
const TEST_KEYS = new Set(['egfr_result','cftr_result']);
const STATE_CHOICES: {value:IntakeAnswerState;label:string}[] = [
  {value:'answered',label:'I have the answer'},
  {value:'unknown',label:"I don't know"},
  {value:'pending',label:'Test pending'},
  {value:'not_tested',label:'Not tested'},
  {value:'not_applicable',label:'Not applicable'},
  {value:'declined',label:'Prefer not to answer'},
];

function AnswerEditor({question,saved,busy,onSave}:{question:FollowupQuestion,saved?:IntakeAnswer,busy:boolean,onSave:(a:IntakeAnswer)=>Promise<boolean>}) {
  const [state,setState]=useState<IntakeAnswerState>(saved?.state||'unknown');
  const [value,setValue]=useState(saved?.value||'');
  useEffect(()=>{setState(saved?.state||'unknown');setValue(saved?.value||'');},[saved?.state,saved?.value,question.fact_key]);
  const selectOptions=question.options.filter(x=>x!=="I don't know");
  const invalid=state==='answered' && (!value.trim() || question.input_type==='number' && (
    !/^\d+$/.test(value) || Number(value)>120
  ));
  return <div className="followup-answer-form">
    <label htmlFor={`state-${question.fact_key}`}>Your answer status</label>
    <select id={`state-${question.fact_key}`} value={state} disabled={busy} onChange={e=>setState(e.target.value as IntakeAnswerState)}>
      {STATE_CHOICES.filter(x=>TEST_KEYS.has(question.fact_key)||!['pending','not_tested'].includes(x.value)).map(x=><option key={x.value} value={x.value}>{x.label}</option>)}
    </select>
    {state==='answered'&&<>
      <label htmlFor={`value-${question.fact_key}`}>{question.question}</label>
      {question.input_type==='select'
        ? <select id={`value-${question.fact_key}`} value={value} disabled={busy} onChange={e=>setValue(e.target.value)}>
            <option value="">Select an answer</option>
            {selectOptions.map(x=><option key={x} value={x}>{x}</option>)}
          </select>
        : <input id={`value-${question.fact_key}`} value={value} disabled={busy}
            type={question.input_type==='number'?'number':'text'} min={question.input_type==='number'?0:undefined}
            max={question.input_type==='number'?120:undefined} maxLength={180}
            placeholder={question.input_type==='number'?'Whole number':'Only what is known; do not guess'}
            onChange={e=>setValue(e.target.value)}/>
      }
    </>}
    <button type="button" className="primary-button" disabled={busy||invalid}
      onClick={()=>void onSave({state,value:state==='answered'?value.trim():null})}>
      {busy?<Loader2 size={15} className="spin"/>:<CheckCircle2 size={15}/>}
      {saved?'Update answer':'Apply to linked trials'}
    </button>
  </div>;
}

export default function TrialFollowups({plan,loading,submitting,error,answers,changed,onSelectTrial,onAnswer,independentReviewCount=0,clarificationModelUsed=false}:Props) {
  const [expanded,setExpanded]=useState<string|null>(null);
  const [editing,setEditing]=useState<string|null>(null);
  const [showUnmapped,setShowUnmapped]=useState(false);
  if (!loading && !error && !plan) return null;
  if (!loading && !error && plan && plan.questions.length===0 && plan.completed_questions.length===0){
    if(plan.unmapped_criteria.length===0)return null;
    return <section className="panel followup-compact" aria-label="Requirements needing clinical review">
      <button type="button" className="followup-reason-toggle" aria-expanded={showUnmapped}
        onClick={()=>setShowUnmapped(!showUnmapped)}>
        <ShieldCheck size={16}/> {plan.unmapped_criteria.length} requirements need clinician review
        <ChevronDown size={14} className={showUnmapped?'rotate':''}/>
      </button>
      {showUnmapped&&<div className="followup-source-list">{plan.unmapped_criteria.map((c,i)=>
        <p key={`${c.nct_id}:${c.criterion_id}:${i}`}><b>{c.nct_id} · {c.criterion_id}</b> — {c.reason}</p>)}
        <p>These questions cannot be resolved safely by the supported automatic rules.</p>
      </div>}
    </section>;
  }
  const renderSource=(q:FollowupQuestion)=>expanded===q.fact_key&&<div className="followup-source-list">
    {q.linked_criteria.map(link=><div className="followup-source" key={`${link.nct_id}:${link.criterion_id}`}>
      <button type="button" onClick={()=>onSelectTrial(link.nct_id)}>{link.nct_id} · {link.criterion_id} <ArrowRight size={13}/></button>
      <span>{link.kind==='exclusion'?'Exclusion':'Inclusion'} requirement</span>
      <blockquote>“{link.source_text}”</blockquote>
    </div>)}
  </div>;
  return <section className="panel trial-followups" aria-label="Trial-specific follow-up questions">
    <div className="followup-heading">
      <div>
        
        <h2>Questions to clarify</h2>
        <p>One answer can update several studies.</p>
      </div>
      
    </div>
    {loading&&<p className="followup-status">Loading study criteria and initial rule-based review…</p>}
    {error&&<div className="intake-error" role="alert"><Info size={16}/> {error}. Existing trial information remains available.</div>}
    {plan&&!loading&&<>
      <div className="followup-summary">
        <span><strong>{plan.questions.length}</strong> remaining shared questions</span>
        <span><strong>{plan.reviewed_trial_ids.length}</strong> trials reviewed</span>
        <span><strong>{plan.unmapped_criteria.length}</strong> requirements need expert interpretation</span>
      </div>
      {changed.length>0&&<div className="followup-changes" role="status"><CheckCircle2 size={17}/>
        <span><strong>{changed.length} criterion {changed.length===1?'status':'statuses'} updated</strong> across {new Set(changed.map(c=>c.nct_id)).size} {new Set(changed.map(c=>c.nct_id)).size===1?'trial':'trials'}. These are preliminary rule checks using fictional self-reported facts, not clinical clearance.</span>
      </div>}
      {plan.questions.length===0?<p className="followup-status">No additional questions identified by the supported rules. This does not mean the patient is eligible; review the remaining requirements.</p>:<div className="followup-questions">
        {plan.questions.map((q,index)=><article className="followup-question" key={q.fact_key}>
          <div className="followup-question-heading"><span className="followup-index">{index+1}</span><div className="followup-question-copy">
            <h3>{q.question}</h3><p>{q.explanation}</p>
            <span className="followup-state">{STATE_NOTE[q.answer_state]||q.answer_state}</span>
          </div><span className="followup-impact">{q.trial_count} {q.trial_count===1?'trial':'trials'}</span></div>
          <AnswerEditor question={q} saved={answers[q.fact_key]} busy={submitting} onSave={a=>onAnswer(q.fact_key,a)}/>
          <button type="button" className="followup-reason-toggle" aria-expanded={expanded===q.fact_key}
            onClick={()=>setExpanded(expanded===q.fact_key?null:q.fact_key)}>
            <FileText size={14}/> Why are we asking? <ChevronDown size={14} className={expanded===q.fact_key?'rotate':''}/>
          </button>{renderSource(q)}
        </article>)}
      </div>}
      {plan.completed_questions.length>0&&<div className="followup-completed">
        <h3><CheckCircle2 size={16}/> Answers applied to trial requirements</h3>
        {plan.completed_questions.map(q=><div className="followup-completed-item" key={q.fact_key}>
          <div><b>{q.question}</b><p>{answers[q.fact_key]?.value||'Answer recorded'} · {q.trial_count} linked {q.trial_count===1?'trial':'trials'}</p></div>
          <button className="secondary-button" type="button" disabled={submitting} onClick={()=>setEditing(editing===q.fact_key?null:q.fact_key)}><Pencil size={14}/> {editing===q.fact_key?'Close':'Edit'}</button>
          {editing===q.fact_key&&<AnswerEditor question={q} saved={answers[q.fact_key]} busy={submitting}
            onSave={async a=>{const ok=await onAnswer(q.fact_key,a);if(ok)setEditing(null);return ok;}}/>}
        </div>)}
      </div>}
      {plan.unmapped_criteria.length>0&&<div className="followup-unmapped">
        <button type="button" className="followup-reason-toggle" aria-expanded={showUnmapped} onClick={()=>setShowUnmapped(!showUnmapped)}><ShieldCheck size={14}/> Requirements needing human review ({plan.unmapped_criteria.length}) <ChevronDown size={14} className={showUnmapped?'rotate':''}/></button>
        {showUnmapped&&<div className="followup-source-list">{plan.unmapped_criteria.map((c,index)=><p key={`${c.nct_id}:${c.criterion_id}:${index}`}><b>{c.nct_id} · {c.criterion_id}</b> — {c.reason}</p>)}</div>}
      </div>}
      <div className="followup-disclaimer"><Info size={16}/><span>{clarificationModelUsed?'The Clarification Agent used AI to prioritize source-linked questions; question content and deduplication remain deterministically validated.':'Shared follow-up questions use deterministic, source-grounded rules.'} {independentReviewCount>0?`${independentReviewCount} trial(s) received independent AI skeptic review; remaining criteria may be unreviewed.`:'Independent AI skeptic review was not completed.'} Self-reported answers are not medical record verification. Unknown and unsupported criteria never become automatic passes. Research prototype — synthetic patients only.</span></div>
    </>}
  </section>;
}
