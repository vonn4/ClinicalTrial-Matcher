# ClinicalTrial Matcher

**Hackaroo 2026 · AI / Data Science · Synthetic research prototype**

ClinicalTrial Matcher explores how a controlled multi-agent retrieval-augmented system might help people discover clinical trials, examine inclusion and exclusion criteria individually, identify missing information, and prepare evidence-based questions for clinicians.

> **Important:** Research/navigation prototype only. **Use synthetic patient descriptions exclusively.** It is not medical advice, clinical validation, or confirmation of clinical trial eligibility. Study teams make final screening decisions. The included replay examples and trial identifiers are **fictional**.

## Current implementation status (v0.1)

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

The launcher installs missing **free** Python/npm dependencies, starts FastAPI and Vite, checks both HTTP servers, submits a *modified fictional patient description*, confirms that the parsed age and condition changed, verifies that the matching trial IDs also change, and opens the React dashboard. Press **Ctrl+C** to stop both servers. It does **not** enable paid features.

If you already have the services running, execute `python run_local.py --check` to verify the **actual input → backend → results workflow**. A stale backend on port 8000 will fail the check; stop the old processes and restart with the launcher. If your browser still shows the old locked demo, hard refresh (**Ctrl+Shift+R**).

**Try it:** select **Interactive sandbox**, choose **Sickle cell** or **Cystic fibrosis**, or edit a fictional patient description yourself. Click **Explore synthetic trials**. The results and extracted profile will update. The original **Lung cancer** example includes three *pre-authored educational* assessments. **Changed profiles never inherit those judgments:** discovery works without an AI key, but eligibility/skeptic decisions remain *not assessed* until a real authorized model is configured. Select **Live registry** for real public ClinicalTrials.gov search (internet required, synthetic patient input only).

**This is not a free-form medical chatbot.** To generate new eligibility and skeptic assessments, explicitly opt into the free-tier Gemini API using the local `.env` setup below; never use real patient information, and do not enable paid billing. Public access remains model-disabled by default.

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
