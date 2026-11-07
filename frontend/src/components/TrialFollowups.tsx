import {useState} from 'react';
import {ArrowRight, ChevronDown, CircleHelp, FileText, Info, ShieldCheck} from 'lucide-react';
import type {FollowupPlan} from '../types';

interface Props {
  plan: FollowupPlan | null;
  loading: boolean;
  error: string;
  onSelectTrial: (id: string) => void;
}

const STATE_NOTE: Record<string,string> = {
  missing:'Not provided in the profile',
  unknown:'Marked unknown in the intake',
  pending:'Test result is pending — not a negative result',
  not_tested:'Not tested — not a negative result',
  not_applicable:'Marked not applicable; discuss whether the study requires it',
  declined:'Patient chose not to answer',
};

export default function TrialFollowups({plan,loading,error,onSelectTrial}:Props) {
  const [expanded,setExpanded] = useState<string|null>(null);
  const [showUnmapped,setShowUnmapped] = useState(false);
  if (!loading && !error && !plan) return null;
  return <section className="panel trial-followups" aria-label="Trial-specific follow-up questions">
    <div className="followup-heading">
      <div>
        <div className="section-eyebrow"><CircleHelp size={15}/> NEXT QUESTIONS · MVP 1.5-B</div>
        <h2>Questions that could clarify your trial matches</h2>
        <p>Each question is traced to an actual requirement in the retrieved studies. Shared questions appear only once.</p>
      </div>
      <span className="followup-phase-tag">Question planning</span>
    </div>
    {loading&&<p className="followup-status">Checking study requirements for missing facts…</p>}
    {error&&<div className="intake-error" role="alert"><Info size={16}/> Unable to generate study questions: {error}. The original trial results are still available.</div>}
    {plan&&!loading&&<>
      <div className="followup-summary">
        <span><strong>{plan.questions.length}</strong> shared follow-up questions</span>
        <span><strong>{plan.reviewed_trial_ids.length}</strong> studies reviewed</span>
        <span><strong>{plan.unmapped_criteria.length}</strong> criteria need expert interpretation</span>
      </div>
      {plan.questions.length===0?<p className="followup-status">No additional questions were identified by the supported rules. This does not establish study eligibility; see the source requirements below.</p>:<div className="followup-questions">
        {plan.questions.map((q,index)=><article className="followup-question" key={q.fact_key}>
          <div className="followup-question-heading"><span className="followup-index">{index+1}</span><div className="followup-question-copy">
            <h3>{q.question}</h3>
            <p>{q.explanation}</p>
            <span className="followup-state">{STATE_NOTE[q.answer_state]||q.answer_state}</span>
          </div><span className="followup-impact">{q.trial_count} {q.trial_count===1?'trial':'trials'}</span></div>
          <button type="button" className="followup-reason-toggle" aria-expanded={expanded===q.fact_key} onClick={()=>setExpanded(expanded===q.fact_key?null:q.fact_key)}>
            <FileText size={14}/> Why are we asking? <ChevronDown size={14} className={expanded===q.fact_key?'rotate':''}/>
          </button>
          {expanded===q.fact_key&&<div className="followup-source-list">
            {q.linked_criteria.map(link=><div className="followup-source" key={`${link.nct_id}:${link.criterion_id}`}>
              <button type="button" onClick={()=>onSelectTrial(link.nct_id)}>{link.nct_id} · {link.criterion_id} <ArrowRight size={13}/></button>
              <span>{link.kind==='exclusion'?'Exclusion':'Inclusion'} requirement</span>
              <blockquote>“{link.source_text}”</blockquote>
            </div>)}
          </div>}
        </article>)}
      </div>}
      {plan.unmapped_criteria.length>0&&<div className="followup-unmapped">
        <button type="button" className="followup-reason-toggle" aria-expanded={showUnmapped} onClick={()=>setShowUnmapped(!showUnmapped)}><ShieldCheck size={14}/> Requirements needing human review ({plan.unmapped_criteria.length}) <ChevronDown size={14} className={showUnmapped?'rotate':''}/></button>
        {showUnmapped&&<div className="followup-source-list">{plan.unmapped_criteria.map((c,index)=><p key={`${c.nct_id}:${c.criterion_id}:${index}`}><b>{c.nct_id} · {c.criterion_id}</b> — {c.reason}</p>)}</div>}
      </div>}
      <div className="followup-disclaimer"><Info size={16}/> <span>Question suggestions only—not eligibility decisions. Answers will be collected once and used to reassess all linked trials in Increment 1.5-C. No new answers are submitted from this panel yet.</span></div>
    </>}
  </section>;
}
