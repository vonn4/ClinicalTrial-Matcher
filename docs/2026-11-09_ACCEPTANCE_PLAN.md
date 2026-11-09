# ClinicalTrial Matcher — November 9, 2026 Acceptance & Rehearsal Plan

**Branch:** \`feat/mvp-2.1-end-to-end-hardening\`  
**PR:** https://github.com/vonn4/ClinicalTrial-Matcher/pull/12  
**Scope:** Official ClinicalTrials.gov study records + synthetic patient details + five-stage agent workflow.  
**Purpose:** Verify the pipeline without making clinical eligibility claims or exceeding free-tier permissions.

## What counts as a passing pipeline?

A complete run is not just "five green checkmarks." It must satisfy:

1. A fictional patient profile is accepted without inventing diagnosis/test results.
2. Discovery returns actual records whose IDs match \`NCT########\` and whose source links open the official registry, or reports a genuine registry outage rather than substituting demo trials.
3. Analyst and Skeptic review the same source criteria independently **when model access and criterion coverage permit**. Their actual inference calls appear in the trace; deterministic-only stages are labeled as such.
4. Unverified exclusions, missing history, complicated criteria and skeptic disagreements remain visible as unresolved or clinical review, never silently clear.
5. The Clarification stage asks only study-grounded questions; a shared answer updates all affected criteria and supports correction.
6. The UI displays actual evidence, disagreements and model usage without claiming clinical verification.
7. CI (backend, frontend build, browser smoke) is green on the exact tested commit.

**Five configured agent roles are not five distinct Google models.** Model execution is conditional; zero model calls means the run used deterministic tools, or model steps were skipped/fell back. Inspect trace details.

## 0. Security prerequisite — before enabling AI

- **Revoke** the API key previously exposed in a screenshot and generate a **new** Google AI Studio key.
- **Rotate** the team access token previously pasted into chat. Use the local wizard with \`--rotate-team-token\`.
- Verify your AI Studio project is eligible for a **free tier and billing is disabled**. Our process call cap does not establish what Google will bill.
- Use **only fictional patient profiles**. Do not upload a real patient's medical or genetic details.
- Never copy \`.env\`, API keys or team token into GitHub, screenshots, the chat, or console logs. The project ignores \`.env\`.

## 1. Pull the tested branch

From your existing Windows VS Code PowerShell terminal:

\`\`\`powershell
git fetch origin
git switch --track origin/feat/mvp-2.1-end-to-end-hardening
git log -1 --oneline
git status --short
\`\`\`

If you already created that local branch, use:

\`\`\`powershell
git switch feat/mvp-2.1-end-to-end-hardening
git pull
\`\`\`

**Pass:** The active branch is 2.1, source files are current, and no tracked files are unexpectedly modified. Untracked \`frontend/package-lock.json\` from local npm is not a matching failure.

## 2. Verify local configuration, and shut down the OLD backend

\`\`\`powershell
python configure_local_ai.py --status
\`\`\`

**Pass:** \`ENABLE_LIVE_AI\`, \`GEMINI_API_KEY\` and \`LIVE_AI_ACCESS_TOKEN\` all say configured. Neither secret is printed.

If they are not configured, run \`python configure_local_ai.py --rotate-team-token\` using a **new private key**.

**Critical:** Editing \`.env\` does not update an already-running Python process. In the terminal that originally started the app, press **Ctrl+C**. If unsure which server owns port 8000:

\`\`\`powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  Select-Object LocalPort,OwningProcess
\`\`\`

Identify and stop only the previous application server, not unrelated processes. Repeat for port 5173 if necessary.

Start the project from the **repo root**, keeping this terminal open:

\`\`\`powershell
python run_local.py
\`\`\`

**Pass:** Backend and frontend startup succeed, and the app is served at http://localhost:5173.

## 3. Open a SECOND terminal and run the diagnostics

\`\`\`powershell
python run_local.py --check
python run_local.py --check-ai
python run_local.py --check-live
\`\`\`

- **\`--check\`:** local API, open condition intake, five agent endpoint contracts and Vite startup.
- **\`--check-ai\`:** compares **local .env** to the **running server**; clearly flags a stale backend. Does **not** contact Google.
- **\`--check-live\`:** contacts the official ClinicalTrials.gov API, retrieves source-confirmed NCT study IDs, checks follow-up/reassessment and runs the five-stage **tool-only** workflow. Requires internet; does not invoke Gemini.

**Pass:** All three exit successfully. Record the displayed NCT IDs, number of candidates, model readiness, and any warning. No test should silently show fictional \`DEMO-###\` studies.

### Optional real Gemini provider probe — explicitly authorized

Only after verifying the **Google project has free-tier access and billing disabled**, run:

\`\`\`powershell
python run_local.py --probe-ai --confirm-free-tier
\`\`\`

This deliberately calls the configured Profile and Analyst/Skeptic Gemini model IDs with **synthetic JSON only**, up to one request per **distinct model name**. It does **not** transmit patient details or show private credentials, and it **does consume real model quota**. The command will refuse to send a request without the extra confirmation flag.

**Pass:** One \`PASS: real Gemini JSON response from ...\` per configured distinct model, followed by provider connectivity confirmation. This establishes basic provider access—not yet the five-agent end-to-end run.

If it fails, note the safe error type and HTTP status (e.g. \`401/403\` credentials/access, \`404\` model unavailable, \`429\` free-tier quota, or connection error). Do not share raw secrets.

## 4. Guided intake with REAL study records (tool-only baseline)

In the browser, hard-refresh with **Ctrl+Shift+R**. Select **Free tool-only review** and **Guided intake**. Enter fictional details:

| Fact | Example |
|---|---|
| Condition | sickle cell disease |
| Age | 29 |
| Diagnosis confirmation | Confirmed |
| Prior treatment | I don't know / unknown |
| Current treatment | I don't know / unknown |
| Genetic test / genotype | Not tested or unknown if prompted |
| City | Kansas City, Missouri (fictional setting) |
| Travel | Flexible / anywhere |

Submit **once**.

**Expected:**
- Real \`NCT########\` identifiers and official ClinicalTrials.gov links (if registry returns eligible recruitment statuses).
- Five trace rows: Patient Profile, Trial Discovery, Eligibility Analyst, Independent Skeptic, Clarification.
- **0 model calls** in tool-only mode—this is correct, not a failure.
- Source-linked requirements, pending/unknown results preserved as unknown.
- No \`Run five-agent workflow\` Play button and no fictional-trial source switch.
- Never interpret a candidate list as a confirmed patient eligibility verdict.

## 5. Actual multi-agent flow (model-assisted)

Set **Model-assisted five-agent workflow** *before submitting* a profile. Enter the **team access token**, not your Gemini key. Use a fictional patient and a disease whose retrieved studies have manageable criterion inventories; a rare-disease study with >24 parsed criteria may intentionally skip model review and remain in clinical review.

**Expected:**
- UI shows \`Gemini configured\` before submission (configuration only).
- On submission, trace reports nonzero model-call attempts if model review was eligible.
- Independent Analyst and Skeptic runs are counted **separately**, without revealing first-agent judgments to the Skeptic.
- For studies with unsupported or overly long requirements, trace details show skips/failures; they are not falsely labeled "model reviewed."
- A model error may lead to an explicit tool-only fallback while preserving official studies and earlier successful work.
- \`potential_match\` never constitutes clinical approval; discrepancies and missing skeptic checks remain review items.

Record the displayed agent stages, model call count, \`model_failures\`, \`criteria_limit_skips\`, and skeptic disagreements.

**Important limitation:** All AI model runs have been tested with offline fake-provider responses in CI. Only this browser test plus the explicit provider probe establishes real Google inference on your configured machine.

## 6. Shared clarification and reassessment

Repeat with **age unknown**, so age can become a follow-up if the retrieved studies have an age requirement.

1. Inspect a shared age question and its **Why are we asking?** source links.
2. Answer **42**, apply once.
3. Verify that all studies linked to age are re-evaluated *independently*.
4. Edit the same answer to **17**; age criteria should update where they impose adult thresholds.
5. Confirm pending genetic tests and prior-treatment uncertainty **remain unresolved**.

**Pass:** The profile and source-linked statuses change coherently, no duplicate age question is introduced, and corrections cannot silently switch to different trials.

Specific live studies and shared-question counts **depend on current registry results**; do not assume a fixed number of age criteria.

## 7. Failure and safety checks

| Situation | Expected behavior |
|---|---|
| Local \`.env\` says enabled but running server says disabled | \`--check-ai\` says **STALE BACKEND CONFIGURATION** with restart instructions |
| Backend is stopped | Diagnostic reports no server reachable, not that Gemini key is wrong |
| User enters wrong local team token | Model request returns HTTP 403, no provider call |
| Gemini model not available or quota exhausted | Provider probe reports safe error/status; matching records a bounded fallback or error |
| Study has too many complex criteria | Deterministic clinical review; \`criteria_limit_skips\` exposed |
| Optional model query expansion fails | Real ClinicalTrials.gov condition search still works |
| Skeptic call fails after Analyst succeeds | Missing independent review is explicitly marked; no inferred agreement |
| Actual ClinicalTrials.gov network fails | No mock study fallback or fake NCT results |
| Model output asserts unsupported medical fact | Evidence validator rejects unsupported positive claims |
| Trial source text contains instructions | Treated as untrusted data, not executable instructions |
| Bad or duplicate NCT IDs | Request rejected, no fabricated trial |
| Token / key appears in a screenshot or chat | Rotate it; do not publish the replacement |

## 8. Automated and repeatable checks (developers)

From repo root:

\`\`\`powershell
python -m pytest -q backend/tests
python -m py_compile run_local.py configure_local_ai.py
cd frontend
npm install --no-audit --no-fund
npm run build
npx playwright install chromium
npm run test:e2e
cd ..
\`\`\`

The Playwright tests intercept backend HTTP calls and exercise the real React UI for:
- Exactly one automatic five-stage run after Quick description.
- No redundant Play button.
- Tool-only vs model-assisted setting correctly sent with the *initial search*.
- Local team token passed only as a header for authorized model runs.
- An official-format NCT study card and trace.

**These are browser/UI integration tests with mock API data.** The backend tests use mocked registry and Gemini responses. Neither implies the outside provider is working; the CLI provider probe and browser live run are separate.

## 9. Evidence to collect for the Hackaroo team

Save **redacted** screenshots or notes for the following, avoiding keys and real patient information:

- Git commit SHA + CI green for backend, frontend and browser job.
- \`--check-live\` result with real NCT IDs and official public source URLs.
- \`--check-ai\` (only presence flags and model IDs, never credentials).
- Optional \`--probe-ai\` showing actual provider JSON response by model name.
- Five-agent trace with model call counts, skipped roles and provider-failure details.
- A study's eligibility source text plus source-linked partial decision.
- An independent Skeptic disagreement or review-required state.
- One shared question affecting multiple studies, before and after correction.
- Metrics or runtime logs **only if actually measured**. CI mock results are not clinical validation.

## 10. Release decision

**Pass to judge rehearsal** only when local registry connectivity, local backend freshness, full intake-to-study UI, and a controlled real-model invocation are verified.

**Release blocker** if: fabricated study fallback appears; a secret reaches GitHub; an exclusion is silently cleared; a missing Skeptic counts as "verified"; browser cannot complete intake; provider key is not rotated; or a failed pipeline is presented as successful.

If model quota or provider availability blocks the live demo, the team may demonstrate deterministic navigation and use a separately labeled, **genuine previously recorded** agent trace—but must never claim that replay is live inference.

**No automated task runs tomorrow** unless a scheduled workflow is separately created. This acceptance plan is ready to execute on November 9, 2026.
