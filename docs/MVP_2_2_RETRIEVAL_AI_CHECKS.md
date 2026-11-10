# MVP 2.2 — Condition relevance and Gemini troubleshooting

**Review branch:** `feat/mvp-2.2-retrieval-model-ux` (PR #13, based on MVP 2.1). Existing working branches and `main` are unchanged.

## Why the apparently unrelated retinal registry appeared

Searching **abetalipoproteinemia** may return official study **NCT02435940 — Inherited Retinal Degenerative Disease Registry**. That study lists **Bassen-Kornzweig Syndrome** as a registered condition. NIH MedlinePlus lists Bassen-Kornzweig syndrome as a documented synonym of abetalipoproteinemia. This is a legitimate condition association, but the study is a broad inherited retinal disease **registry**, not proof of eligibility or a treatment trial.

- Source: https://clinicaltrials.gov/study/NCT02435940
- Medical synonym reference: https://medlineplus.gov/genetics/condition/abetalipoproteinemia/

The new matching filter requires one of three observable trial-level facts:
1. Exact disease name in `conditionsModule.conditions` — *Listed condition*.
2. A curated, publicly documented alias in the registered condition list — *Documented synonym*.
3. Exact disease/alias phrase in the actual study title, summary, or eligibility text — *Mention in study* (weaker evidence).

ClinicalTrials.gov search can return studies through related/MeSH indexing even when the provided study text does not explicitly mention the disease. Those hits are filtered from the user-facing list; neither BM25 nor generic term overlap can promote them to a direct match. Records spanning numerous conditions or named a registry are flagged **Broad registry**. No matching result is ever a claim of clinical eligibility, and source criteria still require independent review.

A tighter filter may return **zero studies** for a rare disease. This means no trial-level-supported match was found **within the bounded recruiting studies returned by the search**, not that no relevant trials exist anywhere.

## What the screenshot's AI trace means

The run showed **five workflow roles completed, one Gemini call attempted, zero completed model reviews**. The Analyst model step failed and the study received deterministic checks instead; there was no independent AI Skeptic review. A green icon on each pipeline boundary previously obscured that distinction. The updated UI flags model failure rather than confusing a completed deterministic fallback with successful inference.

**Why that specific Gemini call failed is still unknown** without the provider HTTP status from your local machine. The improved trace reports the safe category/status and remediation text, without displaying credentials.

Google's Gemini model documentation notes limited access to the older Gemini 2.5 models for some newer projects. The repository defaults may therefore not be accessible through your specific key, even if the key is valid. Check your key's actual model list instead of guessing or enabling a paid tier.

## Windows VS Code — reproduce and resolve

From your current project directory:

```powershell
git fetch origin
git switch --track origin/feat/mvp-2.2-retrieval-model-ux
git pull
python configure_local_ai.py --status
python run_local.py --list-ai-models
```

If already tracking that branch, use `git switch feat/mvp-2.2-retrieval-model-ux` before `git pull`. `--list-ai-models` contacts Google's **read-only model listing endpoint**, does **not** run model inference, and never prints keys. It reports whether the configured Profile and Analyst/Skeptic IDs appear in the list.

If one or both IDs are **NOT LISTED**, choose two compatible model IDs from that output whose **free-tier availability you have verified** in Google AI Studio. Update your ignored local configuration without re-entering the API key or token:

```powershell
python configure_local_ai.py --analysis-model YOUR_AVAILABLE_REASONING_MODEL --profile-model YOUR_AVAILABLE_PROFILE_MODEL
```

These are placeholders, not literal model IDs. Do not choose a paid-only model to make the test succeed.

Stop any old `python run_local.py` servers with Ctrl+C, then restart:

```powershell
python run_local.py
```

In a **second terminal**:

```powershell
python run_local.py --check
python run_local.py --check-ai
python run_local.py --check-live
```

After independently confirming that your Google project has eligible **free-tier access with billing disabled**, explicitly test both configured models:

```powershell
python run_local.py --probe-ai --confirm-free-tier
```

Unlike listing/configuration, the probe makes real non-patient JSON inference requests and consumes provider quota. The probe confirms model connectivity only, not the complete multi-agent pipeline.

## Error categories (displayed beside the affected stage)

| Status | Meaning | Next action |
| --- | --- | --- |
| HTTP 401 | Authentication rejected | Check that the private replacement key is valid |
| HTTP 403 | Permission/access denied | Check API restrictions and whether that model is accessible |
| HTTP 404 | Model unavailable | Run `--list-ai-models`, then configure supported model IDs |
| HTTP 429 | Quota exhausted | Inspect Google AI Studio limits and wait; never bypass the free-tier requirement |
| HTTP 500/502/503 | Upstream provider problem | Retry later; deterministic checks remain clearly marked |
| Timeout/network | No provider response | Check connection and retry |
| Schema/JSON validation | Provider returned unusable structured data | Keep clinical review status; inspect safe trace and retry with a supported structured-output model |

A configured model name or green local readiness check is **not proof of successful inference**. The real test is a completed Analyst and independent Skeptic in the actual execution trace.

## Browser verification checklist

1. Use only a fictional patient. Search **abetalipoproteinemia**, age 22, with previous treatments **unknown**.
2. Confirm any displayed study has an explicit *Why this study appeared* source rationale; NCT02435940, if returned, should be labeled **Broad registry** and explain the documented Bassen-Kornzweig name.
3. Open the source criteria. Unknown retinal-specific facts stay unknown; eligibility must not be inferred from the disease alias alone.
4. Confirm the old MVP/version labels and redundant descriptions are gone. The result cards, source evidence and matching details are prominent. Statistics are available under **View search statistics**.
5. Select **Model-assisted** before intake, enter only your private local team token, and submit. Confirm actual model successes/failures in the concise trace.
6. If the model fails, inspect safe **HTTP status / model error** shown beside Analyst; test `--list-ai-models` and `--probe-ai` with the same local `.env`. Do not share credentials.
7. Re-run using a common condition such as sickle cell disease to confirm matching isn't hardcoded to the rare-disease example.
8. Confirm source-linked clarification and independent Skeptic warnings still prevent unsupported eligibility claims.

## Automated tests

```powershell
python -m pytest -q backend/tests
python -m py_compile run_local.py configure_local_ai.py
cd frontend
npm install --no-audit --no-fund
npm run build
npx playwright install chromium
npm run test:e2e
cd ..
```

CI uses mocked ClinicalTrials.gov and Gemini responses. These tests establish contract, UI, fault-handling and security behavior; they do **not** certify live Google access or actual medical eligibility. Keep `.env` and credentials outside GitHub. Rotate the key and team token previously disclosed.
