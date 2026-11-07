# ClinicalTrial Matcher — Master Product, Engineering, Evaluation & Delivery Blueprint

**Project:** Hackaroo 2026 — AI / Data Science, Build-Your-Own-Idea track  
**Version:** 1.0 planning baseline — November 6, 2026  
**Status:** Approved concept and provisional technology selections; *implementation has not begun*  
**Team:** Four human collaborators working as one team with ChatGPT for research, engineering, testing, documentation, and review  
**Cash budget:** $0, with no paid services and no billing upgrades  
**Deliverables:** Live and offline-capable web demo, public/reviewable source repository, repeatable benchmark and security evaluation, research poster, and final technical report

> **Clinical-use boundary:** This is a research/navigation proof of concept using **synthetic patient descriptions only**. It is not a medical device, clinical decision-support system ready for deployment, diagnosis tool, treatment recommender, or definitive trial eligibility service. The authorized study team makes final participation decisions.

## 0. Executive definition and scope rules

**One-sentence pitch.** A multi-agent RAG system that discovers relevant clinical trials, evaluates inclusion and exclusion criteria individually against a synthetic patient profile, independently challenges its own assessment with a skeptic agent, and turns the evidence into understandable trial comparisons, change alerts, and physician discussion materials.

**Problem.** Serious, rare, and genetically defined conditions can have trials whose eligibility text is lengthy, technical, conditional, and frequently updated. People must understand both whether a study is relevant and whether specific requirements are likely to be satisfied. A general search engine, a relevance score, and a definitive eligibility judgment are three different things; our product must not conflate them.

**Non-negotiable core:**
1. ClinicalTrials.gov study retrieval, official NCT provenance, and reproducible candidate ranking.
2. Patient profile extraction that faithfully preserves explicit facts, contradictions, and unknowns.
3. Individual inclusion *and* exclusion criterion assessment with original verbatim evidence and patient-fact references.
4. An independent skeptic agent that looks for missed exclusions, faulty reasoning, and omitted criteria.
5. Conservative aggregation: any material unknown or dispute stays unknown or in need of review; relevance never implies eligibility.
6. Demonstrable RAG evaluation, including an appropriate TREC retrieval baseline, plus distinct criterion-level labeled testing.
7. Controlled indirect prompt-injection tests using untrusted trial text.
8. Free, locally runnable, deployed, and offline replay modes; no real patient data.

**High-value additions if feasible:** save and compare trials, export clinician discussion briefing, see a trial activity timeline, monitor public study changes, and show in-app updates. **Future-only:** real patient/caregiver accounts, clinician portals, notification delivery, EHR integration, drug approval/research monitoring, and regulatory/clinical validation.

**Prioritization:** P0 = necessary to support the central claim; P1 = valuable final-demo functionality; P2 = stretch; Future = outside hackathon. A P2 feature must never delay a working P0 pipeline.

## 1. Users, boundaries, journeys, and success

**Primary users:** synthetic patient persona, caregiver persona, clinician-facing report reader, judge/evaluator. The hackathon implements no real clinical user accounts.

**User stories and acceptance expectations:**
- As a patient, I can paste a plain-language description and correct an extracted age, diagnosis, treatment, mutation, or unknown field before searching.
- As a patient, I can discover potentially relevant active studies and inspect why a study was retrieved, not just view a numerical match.
- As a patient, I can inspect **each** eligibility criterion with exact study text, patient-fact evidence, status, and a question for my clinician if necessary.
- As a patient, I can see skeptic-raised exclusions or disagreements without the application silently suppressing them.
- As a caregiver, I can save synthetic-demo trials, compare their requirements, and prepare a nonclinical conversation brief for a doctor.
- As a reviewer, I can switch to a research dashboard showing genuine benchmark results, raw metric definitions, experiment settings, sample sizes, failures, and caveats.
- As a judge, I can run a known, clearly labeled replay scenario if the live API or free hosting is unavailable.

**Primary user journey:** synthetic description → editable structured profile → search/filter/rank → shortlist → full criterion extraction/assessment → independent skeptic → deterministic cross-check → preliminary status → interactive evidence explanation → optionally save/compare/export → optional update notice.

**Success is not:** correctly diagnosing a patient; guaranteeing treatment availability; deciding final eligibility; comprehensively indexing every global trial; accurately estimating the chance of acceptance; proving clinical efficacy.

## 2. Product requirements and acceptance criteria

### 2.1 Profile intake (P0)
- Accept natural-language free text and optional structured fields; label every example as synthetic.
- Extract age or age range, sex where relevant, diagnosis, disease stage/subtype, genetic alteration/biomarker (including unknown), past/current treatment, comorbidities, location/travel preference, and user-provided supporting facts.
- Save per-field provenance as **explicitly stated**, **user corrected**, **contradictory**, or **unknown**; do not silently transform conjecture into fact.
- Show users the structured result and allow correction. Do not ask for real names, dates of birth, medical-record uploads, or contact information.
- Use terminology normalization only where defensible; preserve original wording and avoid guessing that two clinically distinct mutations are interchangeable.
- Accept an empty/ambiguous profile gracefully and suggest what information would help rather than returning invented clinical details.

### 2.2 Trial discovery (P0)
- Integrate ClinicalTrials.gov v2 through a backend service; collect NCT identifier, title, condition, study type, recruitment status, phase if present, intervention, locations, age/sex fields, inclusion/exclusion text, study URL, posted/updated metadata, and retrieval timestamp.
- Enforce official-source provenance for each record; normalize missing values and divergent record layouts.
- Use user preferences (geography, willing to travel, recruiting status) as clearly shown filters. Do not hide potentially relevant inactive studies without showing that filter is on.
- Baseline: API search and/or local BM25 ranking among returned candidate records.
- Enhanced: semantic embeddings rerank a sufficiently broad candidate pool; optionally union separate search results if time allows. **Reranking alone cannot recover studies omitted by initial retrieval.**
- Present separate **relevance score** and **preliminary eligibility status**; never display a numerical “percent eligible.”
- Limit detailed live assessment to top three by default, configurable to five under known quotas; show additional results as *retrieved but not assessed*.

### 2.3 Criteria extraction, judgment and evidence (P0)
- Parse inclusion and exclusion sections into a complete enumerated requirement inventory; retain every clause and nested AND/OR, NOT, exception, time window, dose threshold, lab threshold, or clinician-defined ambiguity.
- Represent criteria as atomic conditions plus logical groups where necessary; do not treat an “OR” branch as multiple mandatory criteria.
- Evaluate each criterion with **MET**, **NOT_MET**, **UNKNOWN**, or **NEEDS_CLINICAL_REVIEW**, with a separate distinction between requirement class (inclusion/exclusion) and whether the condition is present.
- Example: exclusion statement “history of condition X” with patient history X **present** means exclusion triggered, not a positively “met eligibility requirement.” Internal representation should include `condition_present=true` and `eligibility_effect=conflict`.
- Quote exact source substrings and store their source document ID, field, and ideally offsets/anchors; store patient fact IDs and the reason for assessment.
- Where a criterion is not assessable from supplied facts (ECOG score, lab value, mutation, washout interval, etc.), return UNKNOWN or NEEDS_CLINICAL_REVIEW, not an assumption.
- Python verifies completeness of criterion IDs, output schema, and that citations actually exist in the source text. If a quote cannot be located, flag evidence invalid and block a positive presentation of that assertion.
- Aggregation: if any verified hard conflict exists, mark **identified conflict**; otherwise if relevant criteria are unknown or disputed, mark **more information / clinical review required**; otherwise **appears compatible with available information**, never “eligible” or “accepted.”

### 2.4 Independent skeptic and reconciliation (P0)
- Use a separate prompt/agent call given the **original** profile and trial criteria; require it to produce an independent criterion map *before* reading the first assessment whenever practical.
- Critically inspect exclusion criteria, contradictory history, conditional exceptions, time windows, missed criteria, invalid evidence, and unsupported statements.
- Deterministic comparator reconciles both maps by stable criterion IDs and reports agreement, corrected errors, introduced errors, or unresolved disputes against a manually reviewed gold standard in evaluation.
- If the skeptic identifies an issue, show an explicit reviewer flag. No automatic reclassification to “compatible” based solely on either agent's confidence.
- MVP: one independent verification pass on every shortlisted study, bounded by model quotas. Future optimization may restrict verification to complex cases after measured evaluation.

### 2.5 Clarification and plain-language explanation (P0/P1)
- Generate targeted follow-up questions connected to specific unresolved criterion IDs; rank by relevance to the eligibility decision and ask users to check with a doctor when needed.
- Any newly supplied synthetic fact must be reflected in the profile and trigger reevaluation of affected criteria; no stale labels after correction.
- Two views: **simple patient language** and **technical evidence language**, both anchored to the exact source and consistent in factual substance.
- Explain study relevance, what was checked, what is missing, what the skeptic flagged, and which source to verify. Avoid treatment advice and “you should enroll.”

### 2.6 Saved trials, physician handoff, and monitoring (P1/P2)
- Bookmark trial IDs in browser storage for **synthetic demo only**, with no identity or real medical text persisted by default.
- Compare two or three selected trials across criteria groups, recruitment status, locations, evidence completeness, unknowns, and update timestamp; do not declare one study medically superior.
- Export a print-friendly, locally generated patient–physician discussion brief containing the synthetic profile summary, official trial links, key unresolved criteria, exclusions, source timestamps, skeptic flags, questions, and clear disclaimers. No automatic transmission to clinicians.
- Track public NCT record changes using last-known content hashes/metadata and periodic scheduled retrieval on an allowlisted set of trial IDs or conditions. Classify **newly observed**, **record updated**, **recruitment changed**, **location changed**, **eligibility text changed**, and **removed/not returned** cautiously.
- “Newly observed by our monitor” is not equivalent to “newly registered at ClinicalTrials.gov.” Distinguish first-public-post date, latest update, and first-observed date.
- In-app alerts can be generated by comparing public snapshots to locally saved study IDs when the app opens; **no claim of background push/email alerts** until an actual opt-in notification delivery system exists.
- Never write synthetic user profiles, watch preferences, or browser-local saved data to a public GitHub repo.

### 2.7 Nonfunctional requirements
- Runs locally on ordinary developer hardware without a GPU; hosted service calls remote free-tier models.
- Accessible keyboard navigation, labels, textual legends, high contrast, responsive mobile/desktop layouts; never encode clinical statuses only with color.
- Deterministic/snapshot-based test mode, bounded inputs, request timeouts, graceful partial failures, and human-readable error messages.
- Fast initial UI rendering; visible progress by stage and usable fallback if the free backend has a cold start.
- Logs redact full profiles by default, and avoid sensitive personal information. No account creation or actual medical records.
- Reproducible research: frozen benchmark versions, fixed experiment configs, model IDs, prompt revisions, record hashes, random seed where relevant, and saved raw (synthetic) predictions.

## 3. Architecture: boundaries, services, and operating modes

**Stack:** React + TypeScript + Vite; Tailwind CSS; Recharts; Python + FastAPI + Pydantic; Google Gemini model(s) on their specifically verified free tier; ClinicalTrials.gov API v2; Python BM25 scorer; optional embedding reranker; JSON/SQLite for local development; pytest and frontend tests; Cloudflare Pages + Render Free; GitHub CI and optional scheduled monitoring.

**Architecture is controlled multi-agent, not autonomous free-form delegation.** Plain Python controls the state machine and retries; the LLM carries out constrained profile extraction, criterion interpretation, and independent verification. External data is always evidence, never instructions.

**Operating modes:**
1. **LIVE:** Real API retrieval and model calls; trial updates current as of the source retrieval time; best for functionality demonstration.
2. **REPLAY:** Versioned synthetic profiles, frozen public trial excerpts, precomputed and labeled result JSON; deterministic, no model or API dependency; clearly marked as replay, never passed off as live.
3. **EVALUATION:** Frozen TREC corpus and labeled synthetic scenarios; configured baselines, standardized scoring, output artifacts; not conflated with contemporary live search.

**Core sequence:** `profile input -> profile parser -> correction checkpoint -> official trial API -> candidate ranking -> criterion inventory -> eligibility agent -> independent skeptic -> deterministic validator and aggregator -> dashboard/report`.

**Failures:** A profile-parsing failure offers manual entry. API outage offers labeled replay. LLM throttling shows limited-service state and optionally cached demonstration outputs. Invalid evidence or missing criteria blocks confident status. Source record mismatch reports stale/revision warning. Frontend always distinguishes **not assessed**, **unknown**, **conflict**, and **not found**.

## 4. Canonical data models and contracts

Use Pydantic server-side and generated/mirrored TypeScript types client-side. Keep schemas stable and versioned. Suggested entities:

- **PatientProfile:** `profile_id` (synthetic opaque ID); `source_text`; `age_years?`; `diagnoses[]` (original phrase + normalized term if verified); `stage?`; `genomic_variants[]` (gene, variant text, status known/unknown); `past_treatments[]`; `current_treatments[]`; `comorbidities[]`; `labs[]` (name/value/unit/date); `location?`; `travel_radius?`; `fact_records[]`; `contradictions[]`; `unknowns[]`; `synthetic=true`; `profile_version`.
- **PatientFact:** stable `fact_id`, field name, original value/text span, normalized value if justified, `provenance`, confidence *of extraction* (not medical certainty), and last edit source.
- **TrialRecord:** NCT ID, official URL, title, source, study status, conditions, interventions, phase, locations, inclusion/exclusion raw text, age/sex structured fields, dates, `retrieved_at`, `content_hash`, `source_version`.
- **SearchResult:** NCT ID, retrieval method, keyword/semantic features, relevance score and rank, filters applied, whether selected for detailed assessment.
- **Criterion:** stable `criterion_id`, `nct_id`, inclusion/exclusion type, verbatim source text, source field, source offsets/anchor, atomic/group type, dependencies and boolean operator, extraction confidence, `requires_clinical_interpretation`.
- **CriterionAssessment:** criterion ID, condition presence (`true/false/unknown`), status (`MET/NOT_MET/UNKNOWN/NEEDS_CLINICAL_REVIEW`), eligibility effect (`supports/contradicts/unresolved`), supporting `fact_ids[]`, exact quote anchor, explanation, limitations.
- **SkepticReview:** independent judgments, missing IDs, evidence objections, disagreement map, suggested clarification, final `review_status`.
- **TrialAssessment:** NCT ID, trial-record content hash, profile version, complete assessment array, review results, preliminary compatibility label, generated at, model/prompt versions.
- **TrialChange:** NCT ID, source timestamp, observed timestamp, before/after hashes, changed field set, source official URL, change summary.
- **ExperimentRun:** experiment ID, dataset/snapshot ID, query/case IDs, baseline/model/prompt versions, run timestamps, usage counters, outputs, label reference, metrics, errors, code commit SHA.

**Example response shape (illustrative only):**

```json
{
  "nct_id": "NCT00000000",
  "synthetic": true,
  "relevance": {"rank": 2, "score": 0.79, "method": "hybrid"},
  "preliminary_status": "MORE_INFORMATION_REQUIRED",
  "criteria": [
    {
      "criterion_id": "NCT00000000-I-01",
      "type": "inclusion",
      "source_quote": "Age 18 years or older",
      "patient_fact_ids": ["fact-age"],
      "status": "MET",
      "eligibility_effect": "supports",
      "explanation": "The synthetic patient's stated age is above 18."
    }
  ],
  "skeptic": {"review_status": "NO_NEW_CONFLICT", "flags": []},
  "source": {"url": "https://clinicaltrials.gov/study/NCT00000000", "retrieved_at": "..."}
}
```

Use actual valid NCT IDs only in real runs; the sample ID and quote above are illustrative. The UI must never interpret the relevance score (0.79) as a likelihood of enrollment.

## 5. Backend API: minimum contract

- `GET /health` — process health and version, no model call.
- `GET /api/v1/config/public` — demo mode and capabilities only; never secrets.
- `GET /api/v1/demo/cases` — approved synthetic profiles and replay-case references.
- `POST /api/v1/profiles/parse` — text -> structured profile and uncertainty; no storage by default.
- `POST /api/v1/trials/search` — validated profile + filters -> ranked official trial candidates, no eligibility claims.
- `GET /api/v1/trials/{nct_id}` — full normalized record, official source URL, retrieval date.
- `POST /api/v1/trials/assess` — validated profile + chosen NCT IDs -> per-trial criterion assessment, skeptic checks, evidence references; strict cap and partial failures.
- `POST /api/v1/analysis/run` — optional convenience end-to-end demo endpoint; reuse service functions, no duplicated logic.
- `GET /api/v1/monitor/snapshot` — current public study-change feed, without personalized private data.
- `GET /api/v1/evaluation/summary` — versioned metrics from a checked-in, published evaluation artifact; do not execute the TREC suite on demand in the public app.
- `POST /api/v1/reports/preview` — optional safe rendering payload; preferred final report export happens in the client.

All endpoints use `api/v1`, JSON schema validation, response size caps, structured error codes, timeouts, and explicit `mode` (`live` or `replay`). For an initially simple architecture, use bounded synchronous requests rather than introducing queues; if latency becomes too high, split profile/search/assessment stages and show progress from the client. Do not promise server-side persistence in free Render storage.

## 6. AI component specification

### Profiling agent
**Input:** synthetic free-text description and optional corrections.  
**Output:** `PatientProfile`, unknown questions, contradictions, source quotes.  
**Rules:** extract rather than diagnose; preserve dates, units, negation, and unknowns; do not create unprovided mutation names or lab values.  
**Tests:** missing age, negated condition, ambiguous drug name, stage unknown, contradictory age, explicit rare variant, unsupported inference.

### Criteria inventory + eligibility agent
**Input:** original canonical trial eligibility text, structured profile, source record/version.  
**Output:** exhaustive criterion inventory and judgments, including group logic, patient fact IDs, exact source quotes.  
**Rules:** evaluate *all* relevant clauses including exclusions, never rely on abbreviated summaries alone, preserve OR/AND grouping and timing constraints, label true ambiguity, avoid medical recommendation.  
**Tests:** conjunctions, disjunctions, negations, washout periods, cutoff boundaries, prior-treatment exception, missing genomic data, absent ECOG/lab values.

### Skeptic agent
**Input:** original patient facts and criterion inventory with source text; independent first-pass evaluation.  
**Output:** its own judgments, discovered omissions, objection list, review decision.  
**Rules:** do not blindly endorse assessment, prioritize hidden exclusions, missing/unsupported evidence, overconfident 'met', and logical exceptions.  
**Comparison:** feed skeptic map and original map to deterministic comparator; report disagreements without assuming skeptic correctness.

### Non-LLM validator/aggregator
Check JSON/Pydantic schema; source quote appears in original field; all required IDs covered; duplicate/omitted criteria; conflicts between source snapshot and assessment; illegal final status when hard exclusion triggered; plausible chronology/units where machine-checkable; maximum run size and call count. Label unresolved results rather than 'fixing' by guessing.

**Model selection:** Keep model IDs in environment configuration and log them for evaluation. Begin with free-tier Gemini Flash for complex interpretation and Flash-Lite for simpler extraction if quality testing supports the split; free Gemini embedding model for semantic reranking. Confirm availability/rate limits in the team's AI Studio project before implementation. Structured JSON does not guarantee medical or semantic correctness; validate all content.

**Budget guards:** cap patient input length, candidate results, criteria volume per call, total retries, calls per analysis, and analyses per session. Never expose model keys to the browser. On `429`, stop/retry with bounded backoff; never automatically switch to a paid model.

## 7. Retrieval and ranking research design

**Live retrieval pipeline:**
1. Extract/normalize condition terms and strongly supported synonyms.
2. Query official API with relevant condition terms and explicit filters (status/location); fetch enough candidates for a meaningful shortlist.
3. Normalize and deduplicate by NCT ID; retain retrieval source metadata.
4. Calculate BM25/relevance features over title, conditions, summary, intervention, and other meaningful text; record every component.
5. Optional semantic rerank with embeddings of the same candidates, maintaining a deterministic fusion formula (e.g., reciprocal rank fusion) and recording its parameters. Do not assume it beats BM25.
6. Apply safety-aware candidate selection; assess top 3 live by default, with top 5 only where quotas/latency permit.
7. Fetch *full original* eligibility text for those shortlisted; the LLM must not assess from a truncated snippet that could conceal exclusions.

**Benchmarked retrieval pipeline:** Freeze the matching historical TREC collection, topics, and qrels. **Do not run the 2022 topics against today's live ClinicalTrials.gov and call that a valid 2022 evaluation.** The 2022 track's qrels use 0=not relevant, 1=excluded, 2=eligible. The archival collection is distinct from the live registry and may require substantial local disk space. Benchmark only after confirming corpus availability, terms of use, and hardware constraints. A smaller exploratory subset is permitted only if labeled explicitly; do not claim full-track comparability.

**Comparators:** B0 raw API-style keyword strategy where applicable, B1 BM25, B2 semantic rerank, B3 hybrid fusion. Hold the query set and evaluation pool constant. Use nDCG@10 (graded relevance with clearly stated gain mapping), Precision@K (define whether grade 1 counts), eligible-trial Recall@K for grade 2 where judgments permit, MRR if relevant, and query-level results. Unjudged documents should not automatically be treated as known negatives without discussing pooling limitations.

**Latency/quality tradeoff:** The reason for semantic reranking must be demonstrated by retrieval metrics; if results do not improve, retain BM25 in the live system and report the ablation honestly.

## 8. Eligibility evaluation and adjudication

**Research questions:**
- RQ1: Does semantic/hybrid retrieval improve finding eligible trials compared with a keyword/BM25 baseline?
- RQ2: Does independent skeptic review reduce missed exclusions or unsupported compatibility judgments?
- RQ3: Does source-grounded validation reduce susceptibility to indirect prompt injection?
- RQ4 (supporting): What latency and free-tier usage tradeoffs arise from multiple agents?

**Datasets:**
- TREC 2022 topics, qrels, and *matching historical corpus* for retrieval only.
- A manually reviewed set of **synthetic** profiles paired with original criterion excerpts for atomic-level labels. Plan 25–60 distinct cases if time allows; do not call these clinically validated and do not fabricate expert review.
- Injected/trusted control pairs for prompt-injection evaluation; use a fixed, versioned set of scenarios.
- Stable live-demo fixtures for user testing that are NOT used to tune the final reported evaluation (avoid leakage).

**Criterion ground truth:** For each case, manually record correct criterion span, status, whether exclusion triggered, supporting patient facts, and expected unknowns. Review conflicting annotations and record adjudication source. If none of the team has clinical expertise, describe labels as **engineering reference labels**, not physician gold standards.

**Metrics:**
- Criterion coverage: inventoried requirements / manually expected requirements.
- Criterion accuracy and per-class precision/recall with confusion matrix; avoid a single metric masking UNKNOWN errors.
- Exclusion-trigger recall and false-negative count (particularly important), false-compatible trial-level summary count.
- Evidence quote exact-match rate and traceability rate.
- Skeptic correction rate: errors corrected / initially wrong cases; regression rate: correct cases made wrong / initially correct; missing criterion recovery.
- Prompt-injection attack success rate (ASR): malicious outcomes achieved / applicable injected cases; report per attack type and false alarm on clean controls.
- Latency p50/p95 by stage and total; model calls, input/output tokens, quota errors, failed runs.

**Fair comparisons:** Fix input profiles, candidate trials, source snapshot, evaluation labels, model configuration, sampling/temperature if controllable, and maximum retries. For 'before vs after skeptic', compare on the **same cases**, not a cherry-picked handful. Report sample sizes, failed/abstained cases, limitations, and potentially bootstrap uncertainty where feasible.

**No fabricated results:** Poster/result plots are populated exclusively by generated CSV/JSON output from executed tests. A placeholder graph must be labeled 'illustrative' and excluded from final findings.

## 9. Security, privacy, and clinical risk controls

**Threats to model and app:** indirect prompt injection in external study records; malicious content posing as agent instructions; false/corrupted evidence; contradictory patient profiles; leaked API key; excessive usage from open frontend; log disclosure; cross-site request misuse; user-facing hallucinated medical advice; stale trial information.

**Controls:**
- Treat trial description as untrusted content in delimited data fields; prompts prohibit instruction-following from retrieved data.
- Allowlist data-source hosts, validate NCT IDs, enforce HTTP request timeouts, and limit redirects; never let a user-provided URL cause arbitrary server-side fetching.
- Keep provider secrets solely on backend, restrict CORS to the deployed frontend, and recognize **CORS is not authentication or abuse protection**.
- Add application-level request caps, max expensive runs/session, a feature flag to disable public live LLM access, and bounded concurrency; if deployed publicly, consider host-level protections beyond in-memory rate limiting because ephemeral multi-instance/restarts can reset state.
- Do not accept, request, store, email, or commit real patient records; no medical uploads.
- Keep browser saved trials synthetic-only and avoid storing raw free-text descriptions persistently.
- Log synthetic case IDs, trial IDs, versions, and error codes; suppress raw free-text by default.
- Put privacy/use limitations prominently in UI and reports; warn that official records may change and eligibility has not been confirmed.
- For injection evaluation, use controlled copies of public-study text, never modify the official registry. Test attacks that try to override eligibility decisions, suppress source quotes, or induce irrelevant instructions; record both clean and injected outputs.

**Go/no-go safety gates:** No raw key in frontend/build artifact; no claimed definitive patient eligibility; no unsupported source quote presented as verified; no exposure of real medical information; unsafe outputs visibly flagged and available for team review.

## 10. Dashboard product specification and analytical visualizations

**Design principle:** Two distinct tabs/experiences—**Patient Explorer** and **Technical Evaluation**—built on the same component system. The patient view promotes comprehension; the technical view promotes reproducibility. Never suggest that a colorful figure implies clinical validity.

### Patient Explorer (P0/P1)
- Header: 'Synthetic demonstration', source last-updated/retrieved timestamp, Live/Replay indicator, disclaimer.
- Intake panel: free text + structured facts with editable source/unknown indicator; profile review checkpoint.
- Search controls: condition, recruiting-status preference, distance/travel willingness, phase where relevant, sort, max detailed analyses.
- KPI cards: retrieved, shortlisted, actually assessed, potentially compatible, unknown/review, identified conflicts, saved, changed since last check. Counts must derive from the same analysis run, not unrelated system totals.
- **Discovery funnel:** all candidate results -> filtered -> ranked shortlist -> fully assessed -> preliminary compatible. Show denominators, not just percentages; counts must be internally consistent.
- **Criterion matrix/heatmap:** rows=criterion categories (or individual criteria in detailed view); columns=trials; statuses=met/conflict/unknown/review/not assessed. Clicking a cell opens the original quote, patient fact, skeptic note, and source link. Text/icons accompany colors.
- **Study cards:** NCT ID/title, recruitment, location, relevance rank/score clearly labeled, preliminary compatibility class, unknown counts, date, official link, bookmark and compare action.
- **Recruitment status chart:** distribution among retrieved/shortlisted trials; clearly label the population being charted.
- **Geographic visualization:** locations table or optional plotted map with verified coordinates only; optional in final, no invented commute-time figures.
- **Change timeline:** what changed and when, distinguishing first posted, last official update, and our monitor's first observation.
- **Comparison view:** 2–3 studies, criterion classes, relevant patient facts, locations, status, missing questions, official links; no treatment ranking.
- **Physician brief:** print/export from current synthetic state, including version, date, NCT IDs, unknowns, disagreements, link provenance, questions; label as discussion aid.
- Accessibility: keyboard, mobile-responsive cards/tables, descriptive chart alternatives, explicit text legend, no color-only labels, no overprecision.

### Technical Evaluation Dashboard (P1)
- Sidebar experiment selector: dataset, experiment ID, run date, model/prompt version, git SHA, n, mode, caveats.
- **Retrieval benchmark grouped bars:** BM25 vs hybrid nDCG@10, eligible Recall@K, Precision@K. Clarify judged labels and denominator.
- **Per-query difference plot:** change in metric for each query; prevents a good average hiding regressions.
- **Confusion matrix:** gold vs predicted criterion statuses, class counts, precision/recall; show the UNKNOWN class.
- **Skeptic before/after chart:** corrected errors, unchanged errors, introduced errors, unresolved cases, and examples with source evidence.
- **Security chart:** attack type vs number tested/succeeded/blocked/abstained; include clean control outcomes.
- **Latency bars/box plots:** profile, retrieval, eligibility, skeptic, validation, total; show p50 and p95 where sample supports it.
- **Coverage/evidence chart:** criteria covered, unsupported quotes flagged, unknowns appropriately preserved.
- **Run detail drilldown:** individual synthetic case, NCT ID, expected label, predictions before and after skeptic, exact evidence/flags.
- Every metric/chart is backed by versioned CSV/JSON. Build one visualization dataset transform reused by dashboard and poster-export scripts.

## 11. Monitoring model: zero-dollar and transparent

**Hackathon implementation:** GitHub Actions retrieves a *bounded public allowlist* of NCT IDs or predefined conditions on a schedule, normalizes publicly available fields, compares hashes to last public snapshots, and generates a sanitized `trial-updates.json` public artifact. The frontend can read this feed, compare it to browser-local saved IDs, and show in-app notices when opened. No personal profiles or preferences travel to GitHub Actions. Do not promise push or email notifications.

**Caveats:** GitHub scheduled jobs may be late or skipped, and public-repository schedules may stop after inactivity. An in-app 'check for updates' action is necessary. GitHub history/public commits are not suitable for private patient records. A stored JSON file is a public-data cache, not a real-time database.

**Possible extension:** When secure user accounts and managed persistence exist, build opt-in notifications with delivery logs, deduplication, unsubscribe, provider permissions, and a separate privacy review. FDA updates are post-hackathon; do not equate a newly approved product with a treatment recommendation.

## 12. GitHub repository and collaboration process

**Repository:** `ClinicalTrial-Matcher` (name provisional). Monorepo with code, reproducible tests, documentation, and poster figures. No assigned individual developer ownership in this blueprint; team works as one entity with reviewed PRs.

```text
ClinicalTrial-Matcher/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── app/                   # routes and layout
│   │   ├── components/            # intake, trial cards, evidence panel
│   │   ├── charts/                # funnel, matrix, benchmark, security
│   │   ├── features/              # profiling, search, compare, watchlist
│   │   ├── api/                   # typed backend client
│   │   ├── types/                 # synced API contracts
│   │   └── styles/
│   └── public/
├── backend/
│   ├── requirements.txt          # later lock dependencies
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/               # FastAPI routers
│   │   ├── config/               # settings, env, mode limits
│   │   ├── schemas/              # Pydantic public/internal models
│   │   ├── agents/               # profile, eligibility, skeptic
│   │   ├── orchestration/        # deterministic pipeline
│   │   ├── retrieval/            # ClinicalTrials.gov, BM25, embeddings
│   │   ├── eligibility/          # parsing, logic, aggregation
│   │   ├── validation/           # evidence, coverage, source checks
│   │   ├── monitoring/           # public-trial diffing
│   │   └── reporting/            # exports/summary payloads
│   └── tests/
├── evaluation/
│   ├── configs/                  # frozen run configs
│   ├── trec/                     # loaders, scores; corpus not auto-committed
│   ├── criterion_cases/          # synthetic labeled examples
│   ├── prompt_injection/         # controlled fixtures
│   ├── runners/                  # one-command experiment scripts
│   ├── results/                  # sanitized measured CSV/JSON
│   └── figures/                  # generated SVG/PNG for poster
├── demo/
│   ├── profiles/                 # explicitly fictional scenarios
│   ├── trials/                   # attributed public-study snapshots
│   └── replay/                   # versioned precomputed outputs
├── docs/
│   ├── MASTER_BLUEPRINT.md
│   ├── ARCHITECTURE.md
│   ├── API_CONTRACTS.md
│   ├── EVALUATION_PROTOCOL.md
│   ├── SECURITY_THREAT_MODEL.md
│   ├── ORIGINALITY_AND_COLLABORATION.md
│   ├── POSTER_OUTLINE.md
│   ├── DEPLOYMENT.md
│   └── DECISIONS.md               # architecture decision records
├── scripts/
│   ├── dev_setup.sh
│   ├── run_demo.py
│   └── export_poster_figures.py
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── pull_request_template.md
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-check.yml
│       └── trial-monitor.yml
└── render.yaml
```

**Branching:** `main` always demo-ready; short-lived `feature/<name>` branches; PR requires tests and a brief description plus screenshots when UI changes. Protected main where supported. Label issues `P0/P1/P2`, `mvp-0` through `mvp-4`, `bug`, `experiment`, `docs`, `security`. Document every material architecture change in `DECISIONS.md`. GitHub Actions CI runs backend tests without external model calls, lint/typecheck, frontend build, and contract tests. API integration/LLM live tests require manual execution to conserve quota.

**README must include:** problem, technical differentiators, scope disclaimer, team, architecture diagram, tech stack and cost assumptions, quickstart, synthetic demo, benchmark caveats, poster/report links, evaluation results, reproducibility instructions, deployment links, privacy, and known limitations. Repository and all source materials must follow dataset licenses/terms and attribution obligations.

## 13. Hosting, free-tier verification and deployment

**Local:** React/Vite on a local dev port, FastAPI on local API port, `.env` only backend, replay can run with zero credentials. Seed synthetic fixtures from `demo/`.

**Frontend:** Cloudflare Pages, GitHub-connected Vite project; build command `npm run build`, artifact `dist`. Free `pages.dev` subdomain, no custom domain. Use only `VITE_API_BASE_URL` as a public frontend configuration variable; never put secrets under `VITE_`.

**Backend:** Render Free Python web service running FastAPI/Uvicorn. Set `GEMINI_API_KEY`, CORS origin, model IDs, call limits, replay/public live flags, and fixed fixture path as backend environment variables. Confirm free status before creation. Expect cold start after ~15 min idle, ephemeral local disk, quota-limited free instance hours, and resource limitations. No persistent patient records in a Render SQLite file.

**AI:** Gemini Developer API free tier using only free-supported text and embedding models; select actual model IDs after an account-level smoke test. Google notes that free-tier submitted content may be used to improve products; synthetic data is compulsory. Limits are per project/model and may vary by account; handle `429` and timeouts. No billing account, paid upgrade, or auto-fallback to billed tiers.

**Monitoring:** Public-data-only scheduled GitHub Action plus manual refresh; public data snapshots may live in repo/generated static artifact. Alert the user within app when new observed changes are available. No privacy-sensitive server state.

**Guardrails for cost:** no payment method when avoidable; explicit provider project usage checks; fixed maximum candidate and trial-assessment counts; disable live mode when quotas tight; no hosted embedding index required; no paid Auth, Redis, Postgres, external map geocoding, notifications, observability, or analytics. **Public URL should default to replay/read-only mode** unless we have effective backend-enforced protection for expensive live requests. Any team-only live endpoint must use proper server-side access control or a private environment—never a secret embedded in React, a query string, or browser local storage. CORS alone cannot protect quota. If provider terms change, use replay mode until a compliant free alternative is selected.

**Deployment acceptance:** local replay always works; deployed frontend loads; health check responds once Render wakes; model key stays server-side; configured CORS plus effective live-request protection; official links work; experiment plots load without API calls; free quota errors show a nonmisleading message; user sees source/staleness and Live/Replay badge. A public landing page may offer precomputed, clearly labeled demonstration cases even when team-only live functionality is restricted.

## 14. Test matrix and quality gates

**Unit:** normalization, age limits, empty fields, exact quotes/offsets, deterministic criterion aggregation, OR/AND rules, ranking stability, dataset loaders, change diff, URL/NCT validation, privacy redaction.

**Agent contract:** profile JSON shape, all expected criteria present, proper UNKNOWN handling, source quote verification, skeptic independent first pass, no unauthorized clinical recommendation.

**Integration:** frontend -> FastAPI -> trial adapter -> response models; fallback on external failure; status flow after profile edit; browser bookmark comparison; export reflects current source version.

**Adversarial:** malicious instruction in eligibility text, contradictory dates, long and nested conditions, irrelevant studies with shared keywords, nonexistent NCT, invalid API shape, quota errors, stale record, truncated criterion text, models returning invalid JSON, wrong source quote, bogus normalized mutation, difficult caregiver-language description.

**Regression rule:** Any change affecting criteria parsing or prompts reruns the synthetic labeled cases. Changes affecting retrieval rerun deterministic benchmark subset. Persist errors and before/after counts. No unreviewed regression in known exclusion examples may be concealed by a higher overall score.

**Accessibility:** keyboard-only navigation for main workflow, explicit labels, chart text alternatives, status text with icons, focus visibility, and mobile viewport smoke tests.

**Governance:** If safety or source correctness fail, choose explicit abstention over unsupported positive eligibility. We measure these abstentions rather than hiding them.

## 15. Milestones, dependencies, and measurable exit gates

### Milestone 0 — Foundation and zero-cost proof (P0)
**Implement:** repo scaffold, lockfile/dependency choices, backend/frontend skeleton, health endpoint, typed schemas, fixture system, free Gemini smoke test, ClinicalTrials.gov API smoke test, `.env.example`, CI workflow.  
**Gate:** clean-clone instructions work; frontend and backend communicate; tests pass; no secret committed; no paid service enabled; replay works without a key.  
**Demo:** open a synthetic profile page and show backend health + source integration.

### MVP 1 — Profile → Trial Discovery (P0)
**Implement:** natural-language parser, correction UI, v2 API adapter, candidate list, search filters, BM25 baseline, source links, basic funnel.  
**Gate:** at least three curated fictional profiles can be corrected, searched, and shown with valid NCT records; API outage offers replay; results clearly distinguish search relevance from eligibility.  
**Demo:** paste profile, review facts, retrieve and inspect studies.

### MVP 2 — Evidence-grounded eligibility (P0; minimum credible technical core)
**Implement:** complete criterion inventory, inclusion/exclusion assessment, source evidence offsets, unknown handling, deterministic validators, preliminary non-definitive status, matrix/drilldown, basic clinician questions.  
**Gate:** the curated suite exercises full criteria coverage, positive/negative/unknown cases, OR/AND and exclusions; no known fabricated evidence passes validator; user can trace each displayed judgment to source and patient fact. Set numerical thresholds only after reviewing fixture difficulty; record failures explicitly.  
**Demo:** show a study's requirement breakdown and why an unresolved biomarker prevents confident classification.

### MVP 3 — Independent skeptic, saved studies, clinician report (P0/P1)
**Implement:** second independent agent, map comparator, flagged exclusions/disagreements, saved-trial and compare interactions, synthetic physician discussion export.  
**Gate:** skeptic's separate outputs are inspectable, disagreements visible, benchmark comparison uses same cases; export is labeled as nonclinical and has official links and source timestamps.  
**Demo:** one seeded missed-exclusion case demonstrates flagging; one ordinary case demonstrates no forced conflict.

### MVP 4 — Measured retrieval, security, monitoring and poster (P0/P1/P2)
**Implement:** optional semantic reranker, fair TREC historical benchmark, criterion and skeptic evaluation, controlled prompt-injection tests, evaluation dashboard, chart/CSV export, bounded public trial-change monitor, final interface polish.  
**Gate:** at least one executed baseline comparison and one executed skeptic/security evaluation with denominators and limitations; poster charts trace to raw results; live/replay deployed links verified; monitoring text accurately describes frequency/first observation.  
**Demo:** end-to-end live or clearly labeled replay, then quantitative results and threat test.

### Freeze and submission
- Lock demo scenario versions and model/prompt/config hashes; record final Git SHA.
- Conduct cold-start/dry-run, simulate quota outage, validate offline replay and report export.
- Finalize README, final report, poster, attribution, originality/collaboration discussion, video/screenshots if required.
- Confirm competition poster dimensions, judging criteria, repository submission rules, and deadline when organizers provide them; do not invent these requirements.

## 16. Poster, visualization pipeline, final report, and presentation

**Poster objective:** communicate problem, system contributions, evidence of measured performance, limitations, and future impact. Use vector/SVG graphics or high-resolution images generated reproducibly from experiment results. No invented numbers.

**Poster sections:**
1. Title, team, concise abstract/problem, synthetic-only note.
2. Motivation: trial-search burden and clinical eligibility complexity.
3. Research questions and technical contributions (RAG, criterion-level evidence, independent skeptic, adversarial testing).
4. Architecture/data flow diagram.
5. Dataset and experimental setup (TREC historical corpus and labeled synthetic criterion cases; sample sizes, model versions).
6. Retrieval benchmark figure: BM25 vs hybrid with valid comparable metrics.
7. Assessment figure: status confusion matrix and missing-exclusion analysis.
8. Skeptic figure: corrections vs regressions vs unresolved results.
9. Security figure: attack success vs defense and clean controls.
10. Brief patient dashboard screenshot and physician report example.
11. Limitations, clinical boundary, transparent novelty/collaboration, references, link/QR code if allowed.

**Plot design:** Each figure has a self-contained title, axis units, denominator `n`, measurement definition, model version, caption, and one takeaway tied to the actual data. Use consistent colors/accessibility labels. Export `SVG` for poster layout, `PNG` for fallbacks, and `CSV` for reproducibility. A dashboard graphic is not a result unless computed from actual observed runs.

**Report structure:** Executive abstract; problem/user context; independently developed concept and competition clarification; prior/parallel problem framing and respectful acknowledgment; scope and medical limitations; architecture choice/tradeoffs; extraction/retrieval/eligibility/skeptic methods; security design; datasets/metrics/experimental protocol; results with failures/ablation and uncertainty; dashboard/product experience; budget/deployment; limitations and threats to validity; future collaboration and work; conclusion; source/attribution appendix; setup and reproducibility appendix.

**Originality/collaboration section:** State factually that the concept was independently developed, a related proposal was later discovered, the team sought clarification and was authorized to proceed, and the projects overlap in their shared goal. Distinguish **our implementation/research commitments** (criteria-by-criteria evidence, independent skeptic, TREC baselines, adversarial testing) from **complementary ideas emphasized by the other proposal** (longitudinal monitoring, caregiver-friendly notification, clinician handoff). If adopting those ideas, credit the influence openly and avoid claiming exclusivity, copying materials, or implying any partnership without agreement. Consider future API interoperability/collaboration as a possibility, not a promised outcome. Keep private organizer correspondence out of public repo unless explicitly permitted.

**Suggested 4–5 minute demo story:** 0:00 problem and unique approach; 0:30 synthetic user intake; 1:00 retrieval and source; 1:30 criterion evidence; 2:15 skeptic catches/flags a seeded challenge; 3:00 saved trial/clinician brief; 3:30 research dashboard with real measured results; 4:15 injection test and limitations; 4:40 impact and collaboration opportunity. Adjust to actual competition time limit.

## 17. Operational risks, tradeoffs, and fallbacks

| Risk | Likelihood / severity | Mitigation and honest presentation |
|---|---|---|
| LLM free quota exhausted | Medium / high | Bounded calls, precomputed replay, visible mode, limited detailed trials; never bill |
| Cold start on free hosting | High / medium | Pre-open API health; client loading; local demo fallback |
| Live study records change | High / medium | Show retrieval date and hash; benchmark frozen snapshot |
| Long/nested eligibility text | High / high | Full text, complete criterion inventory, logical groups, abstain if incomplete |
| Skeptic repeats primary error | Medium / high | Independent first pass and evaluated error/regression counts |
| Retrieval misses rare variants | High / high | Explicit genes/variants, expanded queries, hybrid experiment; avoid claiming comprehensive recall |
| Prompt injection in source | Medium / high | Data/instruction boundary, validation, fixed attack suite, report failures |
| Public endpoint abused | Medium / high | Restrict live demo, call caps, concurrency bounds, disable switch, no keys in client |
| No clinical annotators | High / medium | Engineering reference labels; do not market as clinically validated |
| TREC corpus too large to process quickly | Medium / high | Secure snapshot early; experiment subset labeled exploratory; don't invent full-run results |
| Monitoring schedule missed | Medium / low | Manual refresh, observed timestamp; no guaranteed delivery claim |
| UI overbuilt at expense of reasoning | Medium / high | MVP 2 eligibility evidence is hard core; graphs are a lens on real data |

## 18. Decisions already recommended, details still to verify

**Recommended now:** controlled Python multi-agent orchestration; three specialized LLM roles; official API; BM25 first and semantic comparison later; Pydantic; React/TypeScript/Vite/Tailwind/Recharts; FastAPI; GitHub monorepo; Cloudflare Pages + Render Free; entirely synthetic data; replay mode; no paid dependencies; research-first evaluation.

**Verify when implementation starts:** exact free Gemini model IDs and per-project rate limits; terms of permitted benchmark corpus access/redistribution; event poster size, slide/report format, and deadlines; whether Render and Cloudflare free deployments are available for the team without attaching a payment method; team-level ability to run the TREC corpus locally; official ClinicalTrials.gov field schema details for concrete requests; final public launch mode/access protections.

**Do not assume:** that the best embedding model, best semantic weight, or strongest skeptic will outperform simpler baselines; that all patient medical facts are known; that notification delivery is implemented because a timeline exists; that '0 dollars' means unlimited free use; or that a hackathon prototype is suitable for real clinical decisions.

## 19. Immediate engineering work order (before building features)

1. Establish GitHub repo and master plan as `docs/MASTER_BLUEPRINT.md` (this document).
2. Write `docs/DECISIONS.md` with the provisional architecture and reasons.
3. Implement and test the four shared schemas; generate an illustrative API contract and representative synthetic fixtures.
4. Scaffold FastAPI and Vite/React with a stub endpoint returning fixture results; connect end to end.
5. Confirm zero-billing Gemini free tier and ClinicalTrials.gov v2 access using synthetic inputs; log model IDs and API usage.
6. Create a source-grounded NCT normalization test and a safe, bounded search adapter.
7. Establish unit/typecheck/build CI and replay mode.
8. Begin MVP 1, then advance only when its explicit exit gate is met.

**Definition of the finished hackathon product:** A reliable, clearly labeled synthetic-patient research demonstration that can find and explain studies from official records, evaluate criteria with source evidence, expose independent verification and uncertainty, show honest benchmark/security results, provide a useful dashboard and clinician discussion brief, and work live or from transparent replay—without charging the team or making medical eligibility claims.

---

### Source references to verify during implementation

- ClinicalTrials.gov API v2 overview: https://clinicaltrials.gov/data-api/api
- ClinicalTrials.gov study record downloads/terms: https://clinicaltrials.gov/data-api/how-download-study-records
- NLM API v2 technical bulletin: https://www.nlm.nih.gov/pubs/techbull/ma24/ma24_clinicaltrials_api.html
- TREC 2022 official collection/judgments: https://trec.nist.gov/data/trials2022.html
- TREC 2022 track overview: https://trec.nist.gov/pubs/trec31/papers/Overview_trials.pdf
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Gemini structured outputs: https://ai.google.dev/gemini-api/docs/structured-output
- Render free service restrictions: https://render.com/docs/free
- Cloudflare Pages Vite builds: https://developers.cloudflare.com/pages/configuration/build-configuration/
- GitHub scheduled workflow limitations: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

*This plan is a living engineering source of truth; all experimental scores, dates, implementation status, selected model IDs, and actual live deployment URLs must be filled in from verified work rather than estimates.*
