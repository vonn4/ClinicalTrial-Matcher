# Current development status — MVP 1.5-A

**Branch:** `feat/mvp-1.5-guided-intake` (review against `feat/initial-mvp-v0.1`).

- [x] Guided, synthetic-only patient intake questionnaire with condition-specific questions
- [x] Explicit known / unknown / pending / not-tested / not-applicable / declined states
- [x] Separate prior and current treatment fields; biomarker results are distinct from test mentions
- [x] Canonical structured profile with provenance, unknowns, user review and editing
- [x] Existing quick description mode and fixed synthetic evidence demonstration preserved
- [x] Guided profile discovery uses canonical backend answers; no inherited canned eligibility verdicts
- [x] Backend regression and intake tests; launcher guided-workflow health check
- [ ] Trial-specific question extraction and cross-trial deduplication (MVP 1.5-B/C)
- [ ] Dependent criterion-level reassessment on edits (MVP 1.5-C)
- [ ] Full browser automation and question-burden evaluation (MVP 1.5-D)
- [ ] Real external trial/LLM clinical validation and formal benchmark experiments

**Safety:** Research navigation with synthetic data only. Trial eligibility conclusions are not provided for new guided profiles. Unsupported/unanswered facts are never treated as an eligibility pass.

## Interactive development update

- The replay textarea is now editable; three synthetic condition examples are selectable.
- Original unchanged replay still uses exactly its pre-authored judgments; any modified fictional description uses real server-side deterministic parsing and condition-specific fictional search, with **no fabricated eligibility or skeptic review**.
- `run_local.py`/`run_local.bat` launch both services and verify real input parsing/results instead of checking HTTP status alone.
- Automated backend tests: **25 passed** locally. Frontend npm install/build unavailable in this sandbox because the npm registry cache is incomplete; GitHub CI should run the actual frontend build after the change is pushed.
- No external ClinicalTrials.gov or Gemini API call was used for this offline validation.

# ClinicalTrial Matcher — Implementation status

Date: 2026-11-06. Stage: v0.1 implementation source (not a deployed/clinically validated product).

## Verified in the current environment
- 21 offline Python unit/API tests passed.
- Python sources compile.
- TypeScript/TSX files parsed successfully using the installed TypeScript compiler in transpile-only mode.
- Replay data generated as versioned synthetic JSON; backend and frontend fixtures are synchronized.
- No API keys, billing accounts, subscriptions, domains, or paid services were used.

## Implemented
- Monorepo with a responsive React/TypeScript dashboard and FastAPI backend.
- Canonical Pydantic schemas for patient profiles, trial records, criteria, assessments and independent skeptic findings.
- Public ClinicalTrials.gov API v2 request/normalization and BM25 reranking.
- Optional gated Gemini profiler, eligibility assessor, separate skeptic and evidence checks.
- Fixed synthetic replay and downloadable clinician discussion print view.
- Saved studies in browser local storage, discovery funnel, status overview and research panel.
- Optional Gemini embedding reranker (not enabled or evaluated).
- Public NCT change monitor (opt-in, empty allowlist) and GitHub Actions scheduler.
- Retrieval metrics calculator (requires actual labeled TREC inputs).
- GitHub CI, Render Free and Cloudflare Pages deployment instructions.

## Not yet verified / not yet complete
- React dependency installation/build: npm install timed out in the tool environment. Source syntax parsing is not a full typecheck.
- External ClinicalTrials.gov API calls: no live network verification in this environment.
- Gemini inference and semantic embeddings: no credential provided and no model calls made.
- Eligibility reasoning on real trial criteria: requires synthetic labeled evaluations, logic-parser hardening and validation.
- TREC benchmark: benchmark corpus and matching labels were not downloaded; no performance results claimed.
- Security prompt-injection evaluation: test design and controls exist; no actual model attack experiment has run.
- Live website: neither Cloudflare nor Render has been deployed.
- GitHub remote: new repository creation is not available through the connected GitHub actions; source must be pushed after an empty repository is created.
- Trial monitoring and physician collaboration: only opt-in public snapshot workflow and browser-local handoff; no secure accounts, alerts or clinician delivery.

## Release checklist
- [ ] `npm install && npm run build` on a networked workstation or GitHub Actions
- [ ] Add/verify free-tier model credentials only for synthetic data
- [ ] Confirm ClinicalTrials.gov API responses with actual public NCT records
- [ ] Review branch protection / CI before merging
- [ ] Create empty new GitHub repository and push monorepo
- [ ] Deploy React to Cloudflare Pages and FastAPI to Render Free with `ENABLE_LIVE_AI=false`
- [ ] Conduct TREC retrieval, criterion-label, skeptic and security experiments
- [ ] Generate measured poster charts from experiment artifacts

## MVP 1.5-B (question planning) — implementation in review

- Server-side criterion-to-fact mapping for explicitly recognized source text.
- One shared patient fact produces one follow-up question linked to all
  applicable trial criteria, with exact original source evidence and distinct
  age thresholds preserved; unsupported requirements flagged for review.
- `POST /api/v1/intake/followups` accepts bounded trial IDs, verifies official
  source or own fictional fixtures; no arbitrary client-supplied trial text.
- Frontend displays why each follow-up is asked, which studies are affected,
  pending/not-tested states, and unmapped-criteria notices.
- **Not yet present:** submission of follow-up answers, persistent answer
  storage, incremental criterion reassessment, or independently validated AI.
- 46 backend tests pass in the local test environment; frontend full build
  requires GitHub CI review.
