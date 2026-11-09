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
