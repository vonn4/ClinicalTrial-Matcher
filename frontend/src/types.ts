export type Mode = 'replay' | 'live';
export type Page = 'discover' | 'saved' | 'research';
export type Status = 'met' | 'not_met' | 'unknown' | 'clinical_review';
export type Summary = 'potential_match' | 'needs_information' | 'identified_conflict' | 'clinical_review';
export interface Fact { field: string; value: string; evidence: string; source: 'explicit'|'user_corrected' }
export interface PatientProfile {
  description: string; age: number | null; diagnosis: string | null; stage: string | null;
  biomarkers: string[]; treatments: string[]; location: string | null;
  facts: Fact[]; unknowns: string[]; synthetic: true;
}
export interface Trial {
  nct_id: string; title: string; conditions: string[]; status: string; phase: string[];
  locations: string[]; eligibility_text: string; brief_summary: string;
  updated: string | null; url: string | null;
  source:'clinicaltrials.gov'|'synthetic_fixture'; relevance_score: number; retrieved_at: string|null;
}
export interface Criterion { id: string; kind: 'inclusion'|'exclusion'; text: string; source_text: string }
export interface Assessment { criterion_id: string; status: Status; exclusion_triggered:boolean|null; explanation:string; patient_evidence:string[];question_for_doctor:string|null;verified_evidence:boolean }
export interface Skeptic {criterion_id:string; independent_status:Status; exclusion_triggered:boolean|null; explanation:string; disagreement:boolean}
export interface TrialAssessment {nct_id:string;criteria:Criterion[]; assessments:Assessment[];skeptic:Skeptic[];summary:Summary;unresolved:string[]; provenance:'live_llm'|'synthetic_replay'}
export interface Analysis {mode:Mode;profile:PatientProfile;trials:Trial[];assessments:TrialAssessment[];timings_ms:Record<string,number>;disclaimer:string}
