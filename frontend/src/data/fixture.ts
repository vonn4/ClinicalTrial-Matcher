import replay from './replay.json';
import type { Analysis, PatientProfile, Trial, TrialAssessment } from '../types';
export const sampleDescription: string = replay.description;
export function syntheticPatient():PatientProfile {
  return {description:sampleDescription,age:42,diagnosis:'non-small cell lung cancer',stage:'stage III',
    biomarkers:['EGFR'],treatments:['chemotherapy'],location:'Kansas City, Missouri',synthetic:true,
    unknowns:['biomarker result'],facts:[
      {field:'age',value:'42',evidence:'42-year-old',source:'explicit'},
      {field:'diagnosis',value:'non-small cell lung cancer',evidence:'non-small cell lung cancer',source:'explicit'},
      {field:'stage',value:'stage III',evidence:'stage III',source:'explicit'},
      {field:'treatment',value:'chemotherapy',evidence:'chemotherapy',source:'explicit'}
    ]};
}
export const offlineAnalysis:Analysis={
  mode:'replay',profile:syntheticPatient(),trials:replay.trials as unknown as Trial[],
  assessments:replay.assessments as unknown as TrialAssessment[],timings_ms:{},
  disclaimer:'OFFLINE REPLAY — all studies and assessments are synthetic illustrations, not clinical findings or model evaluations.'
};
