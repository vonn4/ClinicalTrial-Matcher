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
