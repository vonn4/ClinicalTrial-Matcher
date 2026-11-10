import {test,expect,Page} from '@playwright/test';

type Mode='tools'|'model';

const profile={
  description:'Fictional patient aged 42 with multiple sclerosis.',
  diagnosis:'multiple sclerosis',age:42,stage:null,location:null,
  facts:[],biomarkers:[],treatments:[],unknowns:[],synthetic:true,
  intake_answers:{},followup_answers:{}
};
const study={
  nct_id:'NCT12345678',title:'Mocked public study for UI test',
  status:'RECRUITING',phase:[],locations:['Kansas City, Missouri'],
  conditions:['multiple sclerosis'],eligibility_text:'Inclusion Criteria: Adults 18+',
  source:'clinicaltrials.gov',url:'https://clinicaltrials.gov/study/NCT12345678',
  brief_summary:'Only a browser-test fixture',minimum_age:'18 Years',
  match_type:'listed_condition',match_explanation:'Listed study condition: multiple sclerosis',broad_registry:false,
  maximum_age:null,updated:null,retrieved_at:'2026-11-08T12:00:00Z'
};
const assessment={
  nct_id:study.nct_id,criteria:[],assessments:[],skeptic:[],
  summary:'clinical_review',unresolved:['Clinician review required'],
  provenance:'deterministic_followup'
};
const followups={
  reviewed_trial_ids:[study.nct_id],questions:[],completed_questions:[],
  unmapped_criteria:[],mapped_criterion_count:0
};
const agents=['profile','discovery','analyst','skeptic','clarification'];

function resultFor(depth:Mode){
  const trace=agents.map(agent=>({
    agent,execution:depth==='model'&&['analyst','skeptic'].includes(agent)?'model':'tools',
    summary:'Browser-test synthetic orchestration result',
    model_calls:depth==='model'&&['analyst','skeptic'].includes(agent)?1:0,
    duration_ms:1,details:{}
  }));
  return {contract_version:'2.0-A',mode:'live',profile,trials:[study],
    assessments:[assessment],followups,trace,model_calls:depth==='model'?2:0,
    candidate_count:1,profile_concerns:[],changed_criteria:[],
    notice:'Synthetic browser test only; no Google or registry calls were made.'};
}

async function mockedBackend(page:Page, collected:{depth:string,token:string}[], ready=true,failModel=false){
  await page.route(/^http:\/\/(localhost|127\.0\.0\.1):8000\//,async route=>{
    const request=route.request();
    if(request.method()==='OPTIONS'){
      await route.fulfill({status:204,headers:{
        'access-control-allow-origin':'*',
        'access-control-allow-methods':'GET,POST,OPTIONS',
        'access-control-allow-headers':'Content-Type,X-Live-Access-Token'}});
      return;
    }
    const url=new URL(request.url());
    const path=url.pathname;
    let payload:unknown={};
    let status=200;
    if(path==='/health')payload={status:'ok',mode_default:'live',synthetic_only:true};
    else if(path==='/api/v1/registry/status'){
      payload={connected:true,api_version:'v2-test',data_timestamp:'2026-11-08T00:00:00Z'};
    }else if(path==='/api/v1/matching/capabilities'){
      payload={
        agent_roles:agents,tools_available:true,live_model_enabled:ready,model_ready:ready,
        model_provider:'Google Gemini',model_readiness_message:ready?'Configured':'ENABLE_LIVE_AI disabled',
        profile_model:'gemini-2.5-flash-lite',analysis_model:'gemini-2.5-flash',
        max_studies:3,max_model_calls_per_run:9
      };
    }else if(path==='/api/v1/profiles/parse'){
      payload=profile;
    }else if(path==='/api/v1/matching/analyze'){
      const body=request.postDataJSON() as {depth:Mode};
      collected.push({depth:body.depth,token:request.headers()['x-live-access-token']||''});
      const run=resultFor(body.depth);
      if(failModel){
        run.model_calls=1;
        run.trace[2]={...run.trace[2],execution:'tools',model_calls:1,details:{
          model_failures:1,model_error:'model_unavailable',model_http_status:404,
          model_help:'This model is not available to this project; check available models.'
        }};
      }
      payload=run;
    }else if(path==='/api/v1/intake/questions'){
      payload={version:'1.5-A',questions:[]};
    }else{
      status=404;
      payload={detail:'Unexpected browser fixture request: '+path};
    }
    await route.fulfill({status,contentType:'application/json',
      headers:{'access-control-allow-origin':'*',
        'access-control-allow-headers':'Content-Type,X-Live-Access-Token',
        'access-control-allow-methods':'GET,POST,OPTIONS'},
      body:JSON.stringify(payload)});
  });
}

test('quick description automatically runs all five roles once without a Play button',async({page})=>{
  const calls:{depth:string,token:string}[]=[];
  await mockedBackend(page,calls,false);
  await page.goto('/');
  await expect(page.getByText(/Gemini unavailable:/)).toBeVisible();
  await page.getByRole('button',{name:'Quick description'}).click();
  await page.getByPlaceholder(/Describe a fictional patient/).fill(profile.description);
  await page.getByRole('button',{name:'Search ClinicalTrials.gov'}).click();
  await expect(page.getByText('Matching execution trace')).toBeVisible();
  await expect(page.getByText(study.nct_id).first()).toBeVisible();
  await expect(page.getByText('Listed study condition: multiple sclerosis').first()).toBeVisible();
  await expect(page.getByText('MVP 2.0')).toHaveCount(0);
  await expect(page.getByText('5 roles · 0 used AI · 0 model calls · 1 candidates')).toBeVisible();
  await expect(page.getByRole('button',{name:/Run five-agent workflow/i})).toHaveCount(0);
  expect(calls).toHaveLength(1);
  expect(calls[0]).toEqual({depth:'tools',token:''});
});

test('model choice and local team token are passed through the first intake search',async({page})=>{
  const calls:{depth:string,token:string}[]=[];
  await mockedBackend(page,calls,true);
  await page.goto('/');
  await expect(page.getByText(/Gemini settings found/)).toBeVisible();
  await page.getByRole('radio',{name:'Model-assisted five-agent workflow'}).check();
  await page.getByLabel('Local team access token').fill('synthetic-team-token-not-real');
  await page.getByRole('button',{name:'Quick description'}).click();
  await page.getByPlaceholder(/Describe a fictional patient/).fill(profile.description);
  await page.getByRole('button',{name:'Search ClinicalTrials.gov'}).click();
  await expect(page.getByText('5 roles · 2 used AI · 2 model calls · 1 candidates')).toBeVisible();
  expect(calls).toHaveLength(1);
  expect(calls[0]).toEqual({depth:'model',token:'synthetic-team-token-not-real'});
});

test('a failed Gemini call is visibly diagnosed instead of shown as success',async({page})=>{
  const calls:{depth:string,token:string}[]=[];
  await mockedBackend(page,calls,true,true);
  await page.goto('/');
  await page.getByRole('radio',{name:'Model-assisted five-agent workflow'}).check();
  await page.getByLabel('Local team access token').fill('synthetic-team-token-not-real');
  await page.getByRole('button',{name:'Quick description'}).click();
  await page.getByPlaceholder(/Describe a fictional patient/).fill(profile.description);
  await page.getByRole('button',{name:'Search ClinicalTrials.gov'}).click();
  await expect(page.getByText('1 AI stage(s) had problems.')).toBeVisible();
  await expect(page.getByText(/This model is not available to this project/)).toBeVisible();
  await expect(page.getByText(/HTTP 404/)).toBeVisible();
  await expect(page.getByText('5 roles · 0 used AI · 1 model calls · 1 candidates')).toBeVisible();
  expect(calls).toHaveLength(1);
});
