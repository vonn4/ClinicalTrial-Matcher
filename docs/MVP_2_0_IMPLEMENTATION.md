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


---

## Live-only frontend update

The public application now has a single study source: **ClinicalTrials.gov API v2**. The fictional sandbox selector, example disease presets, bundled fake trial records, and pre-populated patient example are removed from the React frontend. The backend's explicit replay mode is retained solely to preserve offline regression tests and benchmark reproducibility. It is not a supported option on the public interface; API defaults are live, and no outage can quietly replace real records with fake ones. The patient profiles used for development and demo remain fictional. The launcher tests local contracts offline, while `--check-live` verifies real registry connectivity and the five-stage matching API. This section supersedes older documentation mentioning an interactive fictional sandbox.

# MVP 2.0 — Five-agent matching implementation

## Scope and truthfulness

This increment creates a **real five-role orchestration path**, not five autonomous chatbots. Each role runs as a distinct, testable service and returns a machine-readable trace. A role marked `tools` used **no language model**, while `model` means an authorized inference call actually occurred. Do not describe tool-only runs as independent AI reasoning.

The normal guided-intake flow enters the tool-only orchestrator by default, including official registry search when `mode=live`. Model-assisted execution is a separate explicit opt-in requiring the server's `ENABLE_LIVE_AI=true`, an access token, a free-tier Gemini key and hard model-call limits. Do not enter real patient data. No paid fallback.

## Roles, dependencies and effect

1. **Profile**: rebuild canonical user-confirmed facts; optionally inspect a narrative for *non-authoritative* possible contradictions. Model text never overwrites user-confirmed facts.
2. **Discovery**: consult ClinicalTrials.gov or synthetic fixtures; search a bounded pre-reviewed synonym probe for known conditions; deduplicate NCT IDs and BM25-rank. No patient clinical details are sent to ClinicalTrials.gov (condition query and study IDs only).
3. **Analyst**: apply the deterministic criterion engine by default. When authorized, analyze the original source criteria with the Gemini model and validate every claim against original study text and explicit synthetic patient evidence. Long or unsupported inventories retain deterministic clinical-review treatment.
4. **Independent Skeptic**: in model mode, performs a separate assessment from the same frozen original inputs; it **does not receive** the primary judgments beforehand. Deterministic reconciliation flags disagreement. Tool-only mode performs source-integrity checks and explicitly does *not* claim independent model verification.
5. **Clarification**: builds exact source-linked cross-trial questions with current canonical keys. Optional LLM may reorder only the already verified keys; question creation/deduplication and application remain deterministic.

The backend limits model inference to **nine requests per run**, with a separate **process-wide hourly cap** (`MAX_AGENT_MODEL_CALLS_PER_HOUR`, default 24) enforced by the agent model adapter. A failure may cause an explicit tool-only fallback and trace, never hidden paid inference. The run does not persist a patient record or secret token.

## Endpoints

- `GET /api/v1/matching/capabilities`: role and limit metadata.
- `POST /api/v1/matching/analyze`: accepts `profile`, `mode` (`replay` or `live`), `depth` (`tools` or `model`), optional `study_ids`, and `max_studies` (1–3). Returns candidate trials, the three-or-fewer reviewed assessments, source-linked follow-ups, agent traces, and actual model-call count.
- `POST /api/v1/matching/clarify`: same fields plus `study_ids` and bounded keyed `updates`. First validates and applies canonical facts to original source requirements, then runs fresh reviews of the **same** shortlist. Returns criterion status changes and the updated agent trace.

Example (no API key; fictional case):

```json
{
  "mode": "replay",
  "depth": "tools",
  "max_studies": 3,
  "profile": {
    "synthetic": true,
    "description": "Fictional patient with non-small cell lung cancer, age unknown.",
    "intake_answers": {
      "condition": {"state": "answered", "value": "non-small cell lung cancer"},
      "age": {"state": "unknown", "value": null}
    }
  }
}
```

If one age answer resolves the source age criteria in multiple trials, submit it through `clarify` using only the returned registered study IDs. The follow-up plan must not invent new disease conditions or trial requirements.

## Recommended browser acceptance

1. Start backend and frontend from this branch. Complete guided intake with a **fictional** lung cancer patient.
2. Confirm the five-stage trace appears with honest `tools` labels in the default mode.
3. On live mode verify official NCT studies and no synthetic fallback; run `python run_local.py --check-live` to verify actual upstream connectivity.
4. Answer a shared question; verify changed criterion IDs and updated trace while preserving study IDs.
5. Explicitly enable model inference locally, with a permitted free-tier project/token, and rerun. Confirm actual model calls, independent skeptic findings, and a bounded call count. Do not describe model behavior as validated until executed and compared against labeled cases.
6. Verify errors/quotas produce explicit fallback or failures, never silent positive eligibility conclusions.

## Offline ablation scoring

`evaluation/evaluate_agent_ablations.py` computes criterion-level scores from actual supplied labels and predictions. This is an evaluation harness, not a completed clinical validation or a source of fabricated model accuracy. See `evaluation/README.md` for required CSV fields.

## Remaining release gates (not claimed complete)

- Clinical-grade criterion coverage / complex compound logic and independently adjudicated reference annotations.
- Full agent ablation and TREC evaluations; the Research Lab must not show fabricated metrics.
- Browser end-to-end automation across live and replay modes.
- Actual internet connectivity, free-model authorization and model execution on developer hardware.
- Public deployment and Hackaroo research poster.

Full source CI uses Python tests and a TypeScript production build. Keep main unchanged until review and manual browser acceptance.
