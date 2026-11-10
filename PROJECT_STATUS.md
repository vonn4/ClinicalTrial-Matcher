## Detailed matching (branch `feat/detailed-matching`, local only)

- **Rules first, model for the rest:** deterministic rules settle recognised criteria (age ranges, FEV1 % predicted, F508del copies, CFTR modulator use, ECOG, informed consent, pregnancy/breastfeeding). The Analyst and Skeptic review only the remainder; a rule verdict always outranks a model verdict. Each assessment carries `source: rules|model`.
- **Model-output guards:** a model "not met" on an alternative ("A OR B") clause, and any met/not-met on conditional or future-intent wording ("intent to prescribe", "if", "unless"), is downgraded to clinical review.
- **Per-study evidence overview** (`overview` on each assessment; shown on cards and in the detail panel): counts of met / not met / open criteria, failed inclusions, reported exclusions, and the top three missing facts. It is **not** an eligibility score.
- **Parsers are deliberately narrow.** A scan of ~60 real studies for each of six conditions found 1.5-6% of criteria are matched by rules; the rest stay in clinical review or go to the model. Age wording must be age-only ("quit smoking for at least 2 years" and "families of patients under 18" are rejected).
- **Local model speed (measured):** with `qwen3:4b` on CPU, one study takes about 3 minutes. Time is dominated by generated tokens (~8.5 tok/s), not prompt processing; fewer criteria per call helps, prompt tweaks did not.
- **Known limits:** the model can still mark a criterion met on a weak quote that appears in the profile; BMI and lab values (hemoglobin, platelets) are not mapped because follow-up number input is whole-number only.

## MVP 2.1 — audit and end-to-end verification (PR #12)

**Active review branch:** \`feat/mvp-2.1-end-to-end-hardening\` (based on 2.0; neither this nor earlier PRs are merged to \`main\`).

- **Fixed:** stale backend detection in \`python run_local.py --check-ai\`; it compares the ignored project-root \`.env\` with the running server and explains how to restart the old process.
- **Added:** optional \`--probe-ai --confirm-free-tier\` for actual Gemini JSON connectivity with **non-patient data only**; requires explicit confirmation of free-tier billing status and makes real quota-consuming requests.
- **Fixed:** independent official-registry discovery survives failed *optional model* synonym selection (without inventing studies); individual Analyst/Skeptic provider failures preserve other successful trial work while marking missing verification and criterion coverage as unresolved.
- **Fixed:** per-trial dashboard/clarification claims now reflect actual independent reviews and optional AI-based question ordering.
- **Added:** backend fault-injection tests, local launcher/security tests, and Chromium Playwright UI integration tests for automatic five-agent execution and correct upfront model selection.
- **Audit guide:** [November 9, 2026 acceptance plan](docs/2026-11-09_ACCEPTANCE_PLAN.md). CI model/provider calls are **mocked**; only the developer's configured Windows machine can certify actual registry connectivity, Gemini inference and live browser interactions.
- **Security:** Revoke the Gemini API key previously exposed in a screenshot; rotate the team access token previously pasted in chat. Do not commit \`.env\` or share secrets.

## Current user-facing workflow: live registry only

- Removed fictional trial mode switch, preset disease buttons, seeded synthetic study cards, and frontend replay fixtures. A user enters any genuine disease name and fictional patient details; all displayed studies must originate from official ClinicalTrials.gov records.
- Unspecified API search/assessment modes now default to `live`, never implicit replay. A registry failure surfaces as an error and never substitutes synthetic studies.
- Backend replay fixtures remain available **only for explicit internal regression experiments**; legacy test endpoints are hidden from API documentation. Synthetic patient profiles remain mandatory for privacy and safe research use.
- Startup smoke tests verify local API/UI contracts; `python run_local.py --check-live` requires internet and tests the real registry plus five-stage matching.

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
