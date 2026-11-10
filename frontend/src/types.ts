export type Mode = 'replay' | 'live';
export type Page = 'discover' | 'saved' | 'research';
export type Status = 'met' | 'not_met' | 'unknown' | 'clinical_review';
export type Summary = 'potential_match' | 'needs_information' | 'identified_conflict' | 'clinical_review';
export interface Fact { field: string; value: string; evidence: string; source: 'explicit'|'user_corrected'|'guided_answer' }
export type IntakeAnswerState = 'answered'|'unknown'|'pending'|'not_tested'|'not_applicable'|'declined';
export interface IntakeAnswer { state: IntakeAnswerState; value: string|null }
export interface IntakeSubmission { answers: Record<string,IntakeAnswer>; narrative: string; synthetic: true }
export interface IntakeQuestion {
  id:string; label:string; help:string; section:'basics'|'history'|'access';
  input_type:'text'|'number'|'select'; options:string[]; conditions:string[];
  required_for_search:boolean; placeholder:string;
}
export interface PatientProfile {
  description: string; age: number | null; diagnosis: string | null; stage: string | null;
  biomarkers: string[]; treatments: string[]; location: string | null;
  facts: Fact[]; unknowns: string[]; synthetic: true;
  intake_answers?: Record<string,IntakeAnswer>; intake_story?:string; followup_answers?: Record<string,IntakeAnswer>;
}
export interface Trial {
  nct_id: string; title: string; conditions: string[]; status: string; phase: string[];
  locations: string[]; location_geopoints?:([number|null,number|null])[]; eligibility_text: string; brief_summary: string;
  updated: string | null; url: string | null; minimum_age?: string|null; maximum_age?: string|null;
  source:'clinicaltrials.gov'|'synthetic_fixture'; relevance_score: number; retrieved_at: string|null;
  match_type?:'listed_condition'|'documented_synonym'|'text_mention'|null;
  match_explanation?:string; broad_registry?:boolean;
  location_fit?:'preferred_city'|'preferred_state'|'preferred_radius'|'outside_radius'|'other_location'|'unknown'; location_explanation?:string;
}
export interface Criterion { id: string; kind: 'inclusion'|'exclusion'; text: string; source_text: string }
export interface Assessment { criterion_id: string; status: Status; exclusion_triggered:boolean|null; explanation:string; patient_evidence:string[];question_for_doctor:string|null;verified_evidence:boolean; source?:'rules'|'model'|null }
export interface Skeptic {criterion_id:string; independent_status:Status; exclusion_triggered:boolean|null; explanation:string; disagreement:boolean}
export interface MatchOverview {total:number;met:number;not_met:number;unknown:number;clinical_review:number;exclusions_triggered:string[];inclusions_failed:string[];resolved_by_rules:number;resolved_by_model:number;top_missing_questions:string[]}
export type ReviewBasis='model_and_skeptic'|'model_analyst_only'|'rules_only';
export interface TrialAssessment {review_basis?:ReviewBasis|null;rules_only_reason?:string|null;overview?:MatchOverview|null;nct_id:string;criteria:Criterion[]; assessments:Assessment[];skeptic:Skeptic[];summary:Summary;unresolved:string[]; provenance:'live_llm'|'synthetic_replay'|'deterministic_followup'}
/** How a study was really reviewed; derived from provenance when an older response lacks review_basis. */
export function reviewBasisOf(a:TrialAssessment):ReviewBasis{
  if(a.review_basis)return a.review_basis;
  if(a.provenance==='live_llm')return a.skeptic.length>0?'model_and_skeptic':'model_analyst_only';
  return 'rules_only';
}
export interface Analysis {mode:Mode;profile:PatientProfile;trials:Trial[];assessments:TrialAssessment[];timings_ms:Record<string,number>;disclaimer:string}

export interface FollowupCriterionLink {
  nct_id: string; criterion_id: string; kind: 'inclusion'|'exclusion'; source_text: string;
}
export interface FollowupQuestion {
  fact_key: string; question: string; explanation: string;
  input_type: 'text'|'number'|'select'; options: string[];
  answer_state: 'missing'|'answered'|'unknown'|'pending'|'not_tested'|'not_applicable'|'declined';
  priority: number; trial_count: number; linked_criteria: FollowupCriterionLink[];
}
export interface UnmappedCriterion {nct_id:string;criterion_id:string;reason:string}
export interface FollowupPlan {
  questions: FollowupQuestion[]; reviewed_trial_ids:string[];
  mapped_criterion_count:number; unmapped_criteria:UnmappedCriterion[]; completed_questions:FollowupQuestion[]; notice:string;
}

export interface CriterionDelta { nct_id:string; criterion_id:string; before:Status; after:Status }
export interface ReassessmentResponse {
  profile:PatientProfile; assessments:TrialAssessment[]; followups:FollowupPlan;
  changed_criteria:CriterionDelta[]; notice:string;
}
