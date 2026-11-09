## MVP 2.0 five-agent core — draft PR #11 (review branch)

- **Implemented in `feat/mvp-2.0-five-agent-core`:** all five roles are executable from the guided-intake workflow: Profile, Discovery, Analyst, blinded Skeptic, Clarification. Tool-only mode uses no LLM and is clearly labeled; separate model-assisted mode requires team authorization and a verified free-tier key.
- **Implemented:** `/api/v1/matching/analyze`, `/api/v1/matching/clarify`, `/api/v1/matching/capabilities`, React agent activity metrics, shared follow-up answer refresh, deterministic evidence checks, bounded registry queries, and per-run/per-hour inference attempt caps.
- **Implemented:** automated offline integration tests and a source-verified dependency inventory. An offline ablation scoring script accepts externally supplied criterion labels and predictions but generates **no claimed research findings** on its own.
- **Unverified:** real-provider Gemini inference, live ClinicalTrials.gov network UAT, in-browser Windows testing, full complex clinical-criteria support, historical TREC experiments, independently adjudicated labels, and production deployment. The tool-only source-integrity check is **not** an independent AI skeptic execution.
- **Workflow:** draft PR #11 targets the previous live-registry feature branch, not `main`.

# ClinicalTrial Matcher — current implementation status

## Official ClinicalTrials.gov API integration (live registry)

- **Implemented:** Official API v2 condition search and ID lookup from FastAPI; arbitrary real disease search labels through guided intake; official NCT IDs, recruitment status, eligibility descriptions, locations, URLs and update dates.
- **Implemented:** public registry version/refresh check (`GET /api/v1/registry/status`), bounded 100-candidate BM25 results, and 10-minute in-memory cache of public studies.
- **Implemented:** live follow-up questions and incremental deterministic partial reassessment use server-resolved public study criteria and official structured age restrictions. Unmapped criteria remain for expert review.
- **Implemented:** offline mocked integration tests and explicit on-machine `python run_local.py --check-live` connectivity test.
- **Validation limitation:** developer container cannot reach the live API network; GitHub CI tests are deterministic mock responses. Real endpoint tests must be executed in the user's connected local environment.
- **Safety:** Synthetic patients only; query terms and NCT IDs go to official registry, not patient answers; no eligibility guarantees, no charges.

## Milestones

- 1.5-A Guided intake: complete.
- 1.5-B Cross-trial follow-up planning: complete.
- 1.5-C Shared answer reassessment: complete.
- 1.6 Live registry integration: implemented; internet UAT required.
- Next: 1.5-D / benchmark, security and usability validation; full live AI remains optional and separate.
