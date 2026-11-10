## MVP 2.4 — Gemini overload recovery and official study-radius filtering

**Isolated review branch:** `fix/mvp-2.4-reliable-ai-radius-search` ([PR #15](https://github.com/vonn4/ClinicalTrial-Matcher/pull/15)), based on the tested MVP 2.3 branch. Neither the last-tested version nor the local private `.env` is modified.

**Why:** In the November 9 Seattle / cystic fibrosis browser test, Gemini returned HTTP 503 while the earlier discovery request succeeded. This indicates temporary upstream service unavailability, **not** that the browser token is invalid. The app now retries one HTTP 503 once after a short delay; every attempt is counted against the nine-call per-run and process hourly limits. After two 503s in one run, it stops contacting Gemini for that run. No paid-tier or unapproved alternate-model fallback is attempted. If Google stays unavailable, the Analyst and Skeptic remain correctly labeled as incomplete. See `python run_local.py --list-ai-models` and the safe model-change instructions below for an explicitly verified alternate free-tier model.

**Location:** A fictional patient selecting **Seattle, Washington** + **Within 250 miles** now triggers ClinicalTrials.gov's *official* `filter.geo=distance(47.6062,-122.3321,250mi)` filter before BM25 and condition evidence ranking. Studies with verified site coordinates show the nearest registered site and approximately how many **straight-line** miles away it is; road mileage and per-site enrollment are never assumed. An empty nearby search stays empty rather than silently filling the page with overseas trials. Other city/state pairs use noncommercial, no-key [Open-Meteo geocoding](https://open-meteo.com/en/docs/geocoding-api) when available, with exact city/region matching and a 24-hour in-memory cache. Only the city/region are sent to the geocoder, never a diagnosis, age, patient story or other facts. Open-Meteo data is for noncommercial use with attribution; review their terms before changing project purpose. When geocoding cannot be verified, discovery uses the official registry's city-text search and **discloses that the numeric radius was not enforced**. Flexible/anywhere travel remains a broad search.

**Verification:** CI uses fake registry/provider calls. Real radius and Gemini availability should be checked from a running local backend with fictional patient input. An HTTP 503 can still occur after the bounded retry; only a successful real Analyst **and** Skeptic trace establishes real model completion.

## MVP 2.3 — Live Analyst/Skeptic and location fixes

**Review branch:** `fix/mvp-2.3-agent-judgments-and-location` ([PR #14](https://github.com/vonn4/ClinicalTrial-Matcher/pull/14)), based on the previously tested MVP 2.2 branch. No earlier branch or local private `.env` is modified.

Gemini Analyst/Skeptic outputs now request a strict JSON schema and use 12-criterion chunks (up to 36 source criteria per study). The backend reserves model-call capacity for the blinded Skeptic, preserving the nine-call cap. When a study is too complex or AI fails, original requirements remain in visibly labeled deterministic clinical review, never silently passed. Location rankings favor registered study sites in the patient's city or state, with clear **distance not verified** messaging; no geocoding or hard mile-radius exclusion is claimed.

**One command to smoke-test real AI (optional, with the server already running):**

```powershell
python run_local.py --smoke-ai-workflow --confirm-free-tier
```

This uses only an embedded **fictional** cystic fibrosis patient and an official public NCT study, consumes up to nine real Gemini inference calls, and reports whether Analyst **and** independent Skeptic both completed. Run only after confirming Google free-tier access and **billing disabled**. It never prints the private API key or team token. Unlike GitHub CI, it verifies real provider inference.

## MVP 2.2 — Cleaner results and model troubleshooting

**Review branch:** `feat/mvp-2.2-retrieval-model-ux` ([PR #13](https://github.com/vonn4/ClinicalTrial-Matcher/pull/13)). The app now explains which disease name was matched in the study's official record, recognizes only documented rare-disease synonyms, and distinguishes broad registries from disease-specific studies. Broad indexing alone no longer makes a study a direct match. The AI execution trace reports safe failure categories and HTTP status instead of presenting failed Gemini calls as successful reviews. Extra MVP labels and repeated explanations have been removed; optional charts are collapsible.

**Troubleshoot on Windows:**
```powershell
python run_local.py --list-ai-models
```
This read-only request lists the models accessible to your local key. If your configured IDs are absent, use `python configure_local_ai.py --analysis-model MODEL_ID --profile-model MODEL_ID` with IDs you have verified support your project's **free-tier quota**. Restart `python run_local.py`, recheck `--check-ai`, and, only after confirming billing is disabled, run `python run_local.py --probe-ai --confirm-free-tier`. The probe consumes real quota.

**Full rationale, setup and acceptance checks:** [MVP 2.2 retrieval and Gemini diagnostics](docs/MVP_2_2_RETRIEVAL_AI_CHECKS.md). Only fictional patient profiles; never commit or share your private `.env`.

## MVP 2.1 — five-agent integration hardening

**Current testing branch:** \`feat/mvp-2.1-end-to-end-hardening\`, draft [PR #12](https://github.com/vonn4/ClinicalTrial-Matcher/pull/12).
Use the [November 9, 2026 acceptance runbook](docs/2026-11-09_ACCEPTANCE_PLAN.md) to verify the entire pipeline.

New in this branch: stale-server-aware \`python run_local.py --check-ai\`, an opt-in, **real** Gemini JSON probe (\`--probe-ai --confirm-free-tier\`), isolated model-failure fallbacks that cannot silently imply eligibility, and automated Chromium browser checks. Backend CI and browser mocks do **not** prove public-registry or provider availability; those must be tested on the developer's computer with fictional patients and a rotated private key.

## Automatically executed five-agent workflow and local Gemini setup

Every **Guided intake** or **Quick description** submission runs the five-stage
Profile → Discovery → Eligibility Analyst → Independent Skeptic → Clarification
workflow **once**. The old separate `Run five-agent workflow` button has been removed.
The mode selection now appears **before** the patient intake.

**Five agent roles are not five installed models.** The roles share a configurable
Google Gemini provider and specialized prompts/tools. In tool-only mode all five
role boundaries execute with **zero LLM calls**. Model-assisted mode makes
conditional inference calls (up to 9 per full run) where needed. The execution
trace reports *actual* calls, not assumed or simulated AI execution.

### Enable model-assisted runs locally (Windows / VS Code)

**First, revoke the Gemini API key exposed in the screenshot and create a new one**
in Google AI Studio. Do not paste the replacement into ChatGPT, GitHub,
a terminal command argument, or the web frontend. Confirm the associated
Google AI project has an eligible **free tier with billing disabled**;
a local model-call cap is not itself a billing guarantee.

From your existing repository folder in VS Code:

```powershell
git pull
python configure_local_ai.py
```

The interactive wizard prompts for your **new API key with hidden input**,
creates or updates the **git-ignored project-root \`.env\`**, sets
\`ENABLE_LIVE_AI=true\`, retains compatible existing settings, and generates
a separate secure team access token. It shows the **team token only** so you can
enter that in the local dashboard. The Gemini key remains in the local backend
file and is never shown in the browser. The wizard makes **no network calls**.

You do **not** need to manually copy \`.env.example\` or choose five API keys.
Five agent roles share the configured Gemini models and make conditional calls.
The template \`.env.example\` retains \`ENABLE_LIVE_AI=false\` as a safe
default; the wizard enables AI **only in your ignored local \`.env\`**.

To inspect the local file without printing either credential:

```powershell
python configure_local_ai.py --status
```

Stop the existing app (\`Ctrl+C\`) and start it again:

```powershell
python run_local.py
```

Then, in a **second** VS Code terminal:

```powershell
python run_local.py --check-ai
```

The latter checks backend configuration **without invoking Gemini**.
Finally, refresh \`http://localhost:5173/\`, select
**Model-assisted five-agent workflow**, enter the **team access token** printed
locally (not the Gemini API key), and submit a fictional patient profile.
Only actual agent trace calls prove that the model service responded.

Model IDs \`gemini-2.5-flash\` (analysis/skeptic) and
\`gemini-2.5-flash-lite\` (profile) are current repository **defaults**, not
a promise that your project can use them; you may edit them in your ignored
\`.env\` after checking free-tier availability. Provider errors may cause a
clearly labeled deterministic fallback; neither this wizard nor \`--check-ai\`
verifies Google connectivity or quota.

**Keep secrets local:** never commit \`.env\`, paste a key in screenshots, or
enter real patient information. To change the team token too, rerun
\`python configure_local_ai.py --rotate-team-token\` with a fresh/current private
API key, then restart.

## Real-study-only interface (current branch)

The public React dashboard searches **official ClinicalTrials.gov API v2 studies only**. The fictional trial sandbox, prefilled lung-cancer patient, and disease shortcut buttons have been removed. Guided intake accepts any real disease or condition name; quick description starts blank. Study results must have official `NCT########` IDs and `clinicaltrials.gov` provenance. Registry errors do **not** fall back to simulated trials.

**Keep the distinction clear:** Study records are real, but patient information entered into this research prototype must remain **fictional/synthetic**. The backend retains explicit replay fixtures only for offline regression tests and reproducible research comparisons; they are not presented or bundled in the user-facing frontend. Historical notes later in this README may refer to previous sandbox releases.

Run `python run_local.py` to launch locally; run `python run_local.py --check-live` in another terminal to verify the actual ClinicalTrials.gov connection and five-stage tool-only workflow. The launcher's normal offline smoke check validates the app without pretending that registry connectivity was tested. Full model-assisted reasoning remains separately opted in.

## MVP 2.0 — Five-agent matching (review branch)

The approved architecture now has five independently testable role boundaries: patient profiling, official trial discovery, eligibility analysis, independent skeptical review, and source-grounded clarification. The **normal guided intake** executes the five-role tool-only workflow at $0. Model-assisted inference is separately gated, bounded and honestly traced. See [implementation notes](docs/MVP_2_0_IMPLEMENTATION.md). **Not clinically validated; do not use real patient information.** Full benchmark, real-model and live-registry UAT remain release gates.

# ClinicalTrial Matcher

**Hackaroo 2026 · AI / Data Science · Synthetic research prototype**

ClinicalTrial Matcher explores how a controlled multi-agent retrieval-augmented system might help people discover clinical trials, examine inclusion and exclusion criteria individually, identify missing information, and prepare evidence-based questions for clinicians.

> **Important:** Research/navigation prototype only. **Use synthetic patient descriptions exclusively.** It is not medical advice, clinical validation, or confirmation of clinical trial eligibility. Study teams make final screening decisions. Internal replay test fixtures are **fictional**, but the public dashboard uses only official registry study identifiers.

## MVP 1.5-C — shared questions and cross-trial reassessment (draft)

Guided intake now flows into **Candidate trials → Shared follow-up questions →
One answer → Independent criterion refresh for every linked trial**. An age
answer can resolve three different trial age rules simultaneously; editing that
answer rechecks those requirements. Pending tests and missing facts never count
as negative results. Original study text remains visible.

**Critical:** New criterion checks are deterministic and based on fictional,
self-reported facts. This is not clinical eligibility, an independently
validated AI review, or a completed skeptic run. Unsupported criteria remain
for clinical review, and no paid API is required. See
`docs/MVP_1_5_IMPLEMENTATION.md` for the API contract and test walkthrough.


## Live ClinicalTrials.gov studies — MVP 1.6 (real study records)

**This is the default mode in the dashboard.** The synthetic patient intake remains the same, but study records now come from the official public ClinicalTrials.gov API v2. No API key or AI model is required to search.

1. Run `python run_local.py` and open `http://localhost:5173`.
2. Verify **Real studies · ClinicalTrials.gov** is selected and the green connection notice reports an API version and registry refresh timestamp.
3. Choose **Guided intake**. Type any real condition name, for example `sickle cell disease`, `cystic fibrosis`, `glioblastoma`, `multiple sclerosis`, or `breast cancer`. **Use fictional patient details only.** There are no preset disease shortcut buttons.
4. Complete the intake; select **Search real trial registry**. The result cards should contain **NCT########** identifiers, `OFFICIAL STUDY` labels, original titles, recruitment status, public locations, and links to official studies (not `DEMO-###`).
5. Trial-specific questions and the limited source-grounded partial rule review now use server-resolved official trial requirements. The official eligibility module's minimum/maximum age limits are retained and can trigger a shared age question. Unsupported complex requirements are explicitly left for clinical review.
6. To run a repeatable **actual-internet integration test** in a *second terminal* while the app is running, execute:

```powershell
python run_local.py --check-live
```

This checks the official `/api/v2/version` response, searches recruiting sickle-cell studies, verifies returned NCT IDs/official source links, reads original criteria and submits an empty partial reassessment. **Unlike CI, it really needs internet access and may fail if the registry is unavailable.** It uses only fictional patient details.

**Data boundary:** The registry receives only the disease search term and requested NCT IDs; the backend does not send the patient's intake or answers to ClinicalTrials.gov. The in-memory cache contains only public trial records for up to ten minutes. It is not a patient database, and no personal information should be entered.

**Interpretation:** A search hit is not clinical eligibility. BM25 only ranks a bounded set of returned studies (at most 100 registry candidates); not all matching studies are guaranteed to be searched. Our deterministic follow-up engine recognizes only a small allowlist of exact criterion structures and official age limits. Unsupported or ambiguous requirements stay unresolved. Live Gemini/independent skeptic, when separately enabled, is not needed for this public registry workflow.

**If live search fails:** Check `http://localhost:8000/api/v1/registry/status`, network access, and the terminal error. Do not switch to mock studies: the user interface is real-registry-only. Internal test fixtures remain available for reproducible regression tests, never as a live-search fallback.

## Current implementation status (MVP 1.5-C staged)


| Feature | Status | Notes |
| --- | --- | --- |
| FastAPI + Pydantic contracts | Implemented/tested | `/docs`, `/health`, `/api/v1/*` |
| React + TypeScript dashboard | Source implemented; npm build not yet verified here | Clinical results, evidence, analytics and saved view |
| Offline synthetic replay | Implemented/tested | Includes 3 explicitly fictional studies |
| Live ClinicalTrials.gov study search | Implemented; external API not exercised in sandbox | Official API v2 + BM25 scoring |
| Patient profiling | Deterministic extractor tested; optional LLM extractor | Must ground every claim in patient text |
| Eligibility and skeptic | Implemented API/code; not live-model validated | Independently invokes Gemini twice, verifies quote provenance |
| Evidence validation | Implemented/tested | Coverage, exact-source checking, unknown fallback |
| Optional semantic reranking | Code implemented; not integrated as default / not benchmarked | Bounded pool and free Gemini embedding API |
| Saved trials / clinician printout | Implemented in UI | Synthetic browser-local only |
| Trial monitoring | Opt-in script/workflow implemented | Needs configured actual NCT IDs and run |
| Research metrics | Metric scripts implemented; **no experiments run** | Dashboard intentionally shows no fabricated numbers |
| Public hosting | Config and instructions provided; **not deployed** | Cloudflare Pages + Render Free |

## Increment 1.5-B — shared trial-specific follow-up questions (retained)

After completing **Guided intake** and discovering fictional trials, the dashboard
now shows **Questions that could clarify your trial matches**. Each question
is mapped to exact server-owned inclusion/exclusion source lines. The same
canonical fact (for example, age) generates just **one question for all linked
trials**, even when their thresholds differ. Click **Why are we asking?** to
inspect every affected trial and its original criterion.

To demonstrate cross-trial deduplication, enter non-small cell lung cancer but
set age to **I don't know**, then submit. The age question is linked to
DEMO-001, DEMO-002, and DEMO-003. Entering an age *during baseline intake*
removes that question from the follow-up queue. EGFR **pending** and **not
tested** remain distinct from negative. Complex/unsupported criteria are
flagged for human review rather than silently inferred.

**Scope:** This stage is a **question-planning preview**. It does NOT yet
collect follow-up answers, update eligibility statuses, or invoke Gemini.
Answer submission and independent per-trial reassessment belong to **1.5-C**.
The demo uses fictional patients/studies only, no paid API or clinical advice.

New endpoint: `POST /api/v1/intake/followups` accepts only trial IDs and a
synthetic patient profile. The backend always loads criteria from its own
fixtures or the official public registry; the caller cannot inject criteria.
Run `python -m pytest -q backend/tests` to verify behavior.

## Run and verify the interactive app (recommended)

From the repository root, **use one launcher instead of starting two terminals manually**:

```powershell
# Windows PowerShell or Command Prompt
py -3 run_local.py
# Alternatively, double-click run_local.bat
```

```bash
# macOS/Linux
python3 run_local.py
```

The launcher installs missing **free** Python/npm dependencies, starts FastAPI and Vite, checks both servers, verifies intake and fictional retrieval, checks cross-trial question deduplication, submits one age answer that must update three trial criteria, and opens the React dashboard. Press **Ctrl+C** to stop both servers. It does **not** enable paid features.

If you already have the services running, execute `python run_local.py --check` to verify the **actual input → backend → results workflow**. A stale backend on port 8000 will fail the check; stop the old processes and restart with the launcher. If your browser still shows the old locked demo, hard refresh (**Ctrl+Shift+R**).

**Try it:** select **Interactive sandbox**, choose **Sickle cell** or **Cystic fibrosis**, or edit a fictional patient description yourself. Click **Explore synthetic trials**. The results and extracted profile will update. The original **Lung cancer** example includes three *pre-authored educational* assessments. **Changed profiles never inherit those judgments:** discovery works without an AI key, but eligibility/skeptic decisions remain *not assessed* until a real authorized model is configured. Select **Live registry** for real public ClinicalTrials.gov search (internet required, synthetic patient input only).

**This is not a free-form medical chatbot.** To generate new eligibility and skeptic assessments, explicitly opt into the free-tier Gemini API using the local `.env` setup below; never use real patient information, and do not enable paid billing. Public access remains model-disabled by default.

## MVP 1.5-A — Guided synthetic intake (new feature branch)

This increment adds a **guided baseline questionnaire** alongside the original **Quick description** demo:

1. Go to **Discover trials → Guided intake**. Enter a fictional diagnosis, or select NSCLC / sickle cell / cystic fibrosis.
2. The questionnaire branches by condition (for example EGFR/ALK for NSCLC, genotype for sickle cell, CFTR for cystic fibrosis).
3. Mark any unknown, pending, not-tested, inapplicable, or declined answer explicitly; do not guess a medical fact.
4. Complete treatment and travel preferences; optionally provide a fictional free-text story.
5. **Review profile** to inspect the facts before clicking **Discover fictional trials** or **Search real trial registry**.
6. In sandbox mode, fictional candidate trials are returned. **Guided cases do not receive fabricated eligibility assessments**. The original Quick description lung-cancer fixture retains its pre-authored illustrative findings.

**Architecture and current scope:** `GET /api/v1/intake/questions?condition=...` serves an explainable question bank; `POST /api/v1/intake/profile` builds canonical, versioned-by-schema patient facts from explicit answers; these are carried through existing discovery APIs. No database, new service, model key, or payment is required. The optional story is retained as unverified context and does **not** overwrite structured facts. When a profile is submitted later, the backend reconstructs its canonical attributes from the original answers instead of trusting a client-supplied age/diagnosis.

**Next planned increments (not yet implemented):** **1.5-B** source-grounded trial-to-fact mappings and missing-question queue; **1.5-C** cross-trial question deduplication and dependent-criterion reassessment; **1.5-D** end-to-end UX, comparison improvements, and empirically tested question efficiency. See `docs/MVP_1_5_IMPLEMENTATION.md`.

## Start locally — no API keys or payment

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/health` or `http://localhost:8000/docs`.

**Frontend** (Node 20+):

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The original replay remains bundled when the backend is unavailable; edited fictional profiles require the running backend.

**Backend tests**:

```bash
cd backend
python -m pytest -q tests
```

No Gemini API key is required for replay, synthetic fixtures, backend tests, or public ClinicalTrials.gov discovery.

### Public clinical trial discovery

In React, select **Live registry** and enter a **synthetic** patient description that explicitly names a supported diagnosis. Click **Search ClinicalTrials.gov**. It retrieves current official study identifiers, source links, metadata, and keyword-ranked studies. **These results are not eligibility assessments.**

The basic deterministic profiler only recognizes a small known set of diagnoses and facts; expand its structured vocabulary or enable the optional model before broadening the audience. Use `http://localhost:8000/docs` to inspect typed API contracts.

### Optional live Gemini eligibility + skeptic (local only)

1. Use a Google AI Studio project with a **confirmed free API tier and no paid billing**. Free-tier input may be used to improve Google products. Use fictional/synthetic data exclusively.
2. Set environment variables on your **local backend process** (for example via `uvicorn ... --env-file ../.env` from the `backend/` directory). Copy `.env.example` to `.env` in the repo root.
3. Set `GEMINI_API_KEY`, `ENABLE_LIVE_AI=true`, and a long random `LIVE_AI_ACCESS_TOKEN` (16+ characters). Set `MAX_LIVE_AI_REQUESTS_PER_HOUR` conservatively. Never put a Gemini API key in frontend code.
4. In React **Live registry**, enter the team access token in the optional password field, then search and run eligibility + skeptic.
5. Observe quota/timeout failures; the app will not automatically upgrade to paid services.

This is not a secure production medical application. Keep the hosted public backend in replay/public-search mode with `ENABLE_LIVE_AI=false` unless strong production-grade identity, quota, and abuse controls are built.

## Main architecture

```text
React dashboard
  |
  v
FastAPI controller / Pydantic source contracts
  +-- synthetic patient extraction (deterministic or opt-in LLM)
  +-- official ClinicalTrials.gov API v2 retrieval
  +-- BM25 ranking (optional embedding reranker)
  +-- eligibility LLM -> criterion assessment & exact evidence checks
  +-- independent skeptic LLM -> disagreements
  +-- conservative status aggregation
  +-- patient dashboard, saved-trial handoff, research lab
```

The precomputed synthetic replay is a **UX/engineering demonstration, not an experimental model performance measurement**. Live model results require explicit opt-in.

## API endpoints

- `GET /health`
- `GET /api/v1/demo/cases`
- `POST /api/v1/profiles/parse`
- `POST /api/v1/trials/search`
- `GET /api/v1/trials/{nct_id}`
- `POST /api/v1/trials/assess` (live protected)
- `POST /api/v1/analysis/run` (live protected)
- `POST /api/v1/intake/reassess` (source-restricted shared answers and partial criterion refresh)
- `GET /api/v1/monitor/snapshot` (inactive until configured)
- `GET /api/v1/evaluation/summary` (reports not measured until experiments run)

## Evaluation and poster

`evaluation/README.md` specifies historical TREC retrieval testing with benchmark files and a real metrics calculator. Criterion-level labeling and prompt-injection experiments must be conducted separately before presenting empirical conclusions. No fictitious scores are included. See `docs/POSTER_AND_REPORT.md` for the final scientific poster/report plan and the respectful competition/originality narrative.

## Hosting at $0

- **Frontend:** Cloudflare Pages (React static files)
- **Backend:** Render **Free** Web Service (Python API)
- **Monitoring:** GitHub Actions (public registry metadata only, empty by default)
- **Source:** GitHub public monorepo

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for precise settings and caveats. **Do not attach a billing method or enable paid resource upgrades.** Free-tier availability and quotas can change; service interruption is preferable to unexpected charges.

## Repository guide

```text
backend/app/      FastAPI, schemas, profiler, retrieval, agents and validation
backend/tests/    Contract and safety tests (offline)
frontend/src/     React app, charts, trial cards, evidence explorer
frontend/src/data Bundled synthetic replay
scripts/          Public-trial monitoring utility
demo/             Generated fictional cases and regeneration script
evaluation/       Experimental protocol and metrics calculator
monitor/          Public study ID allowlist and optional snapshots
docs/             Original master blueprint, poster, deployment
.github/workflows CI and opt-in public registry monitoring
```

## Respectful independent development

ClinicalTrial Matcher was conceived independently; afterward, the team identified another proposal addressing related rare/genetic clinical trial navigation problems. The organizers expressly permitted our track to proceed. Our distinct technical focus is criterion-level evidence-grounded eligibility interpretation, independent skeptical verification, retrieval benchmark comparisons, and prompt-injection evaluation. The complementary proposal emphasized proactive caregiver alerts and clinician communication; we respectfully acknowledge its influence on features added to this roadmap and welcome future collaboration without implying any current partnership. See `docs/POSTER_AND_REPORT.md`.

## Next implementation gates

- [x] Milestone 0: local source structure, schemas, tests, replay, and hosted configuration
- [x] MVP1 source: profile → official trial search + dashboard; **live API/browser build verification pending**
- [ ] MVP2: validate Gemini output on a curated synthetic criterion set, harden nested logical criteria, implement full evidence coverage
- [ ] MVP3: empirically validate independent skeptic, improve trial comparison and correction loop
- [ ] MVP4: real TREC corpus, hybrid retrieval comparison, injection evaluation, poster data and figures, production-ready zero-cost demo protection

## External data and documentation

- [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api)
- [Gemini API pricing and free-tier conditions](https://ai.google.dev/gemini-api/docs/pricing)
- [Cloudflare Pages React guide](https://developers.cloudflare.com/pages/framework-guides/deploy-a-react-site/)
- [Render free-tier limitations](https://render.com/docs/free)
