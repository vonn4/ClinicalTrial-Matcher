# Ollama performance, eligibility, evaluation and poster evidence — 2026-11-10

## Branches and provenance
- **Protected working baseline (no edits):** `feat/ollama-local-agents`
- **Improvement branch:** `feat/ollama-performance-evaluation-poster`
- **Review:** https://github.com/vonn4/ClinicalTrial-Matcher/pull/19
- All patients are fictional. All displayed real studies must originate from ClinicalTrials.gov. No billable cloud inference is required for Ollama.

## What the team actually observed
During a manual browser run on 2026-11-10, a fictional 39-year-old profile with Bardet–Biedl syndrome returned official recruiting study `NCT07674290`, with five completed stages and two model-assisted reviews (Analyst and independent Skeptic), from two model attempts, using local `qwen3:4b`. This is **one demonstration**, not an accuracy trial. The browser screenshots are the evidence source.

The review also exposed a potential false-positive age exclusion: "patients younger than the age approved for treatment with setmelanotide" was treated as triggered merely given the patient's age. The source statement does **not** supply an explicit approval age. This is now forced to clinical review until verified, regardless of the model's apparent confidence. Simple explicit numerical age contradictions are also downgraded rather than reported as fact.

## Implemented improvements
1. In-memory per-request progress tracking with random UUID IDs: profile, discovery, analyst, skeptic, clarification. No patient or study contents are stored in this telemetry.
2. Browser polling shows the **actual current stage** and elapsed time. It does not fabricate future steps or ETA.
3. Model-assisted browser runs default to **one reviewed study** to reduce CPU inference workload; the user can select two or three. Other discovered candidate studies remain visible, but unreviewed studies are not represented as AI-reviewed.
4. The browser request deadline for model runs is extended to 10 minutes, to avoid premature client cancellation during slow local CPU processing; it is *not* a promise of completion in that time.
5. Export button downloads **anonymous run metrics** (stage timings, study IDs, counts and review status) without the fictional patient's fields, prompts, criterion text, access tokens or keys.
6. Age-source safeguards require manual review for unspecified treatment approval ages and age-decision contradictions; missing evidence remains unknown.
7. `run_local.py --check-ai` and `--list-ai-models` recognize local Ollama and verify `qwen3:4b` via loopback, without checking a cloud API key.

## How to start (Windows, PowerShell in VS Code)
Do not change `feat/ollama-local-agents` directly.

```powershell
git fetch origin
git switch feat/ollama-performance-evaluation-poster
git pull --ff-only origin feat/ollama-performance-evaluation-poster
python configure_ollama.py
python run_local.py
```

In a **second** terminal:

```powershell
python run_local.py --check
python run_local.py --check-ai
python run_local.py --list-ai-models
```

Browse http://127.0.0.1:5173. Choose model-assisted, **1 study**, and enter only the browser team token from local `.env` (never an API key). Use fictional BBS age 39, location Seattle, travel flexible/anywhere. Expect a genuine recruiting NCT study **if the current registry returns one**; registry results may change.

During processing, verify each real stage appears. After completion, verify actual Analyst and independent Skeptic model review, not just five tool stages. The per-stage time is shown under Stage details. Click **Export anonymous timing evidence** and save its JSON for the report.

## Repeatable scientific evaluation
```powershell
python -m pytest -q backend/tests
python evaluation/security_tests/run_local_probes.py --dry-run
python evaluation/security_tests/run_local_probes.py --model qwen3:4b --include-skeptic
python evaluation/summarize_local_runs.py path\to\clinicaltrial-matcher-run-metrics.json
```
The security probe makes **4 local Ollama model calls** with fully fictional source text. It reports markers and safety validation outcomes; it is not a peer-reviewed injection success rate. The latency summarizer only uses uploaded/exported real measurements, reports sample sizes, and does not claim speedup without comparable baseline measurements.

For retrieval, run `evaluation/evaluate_retrieval.py` against actual versioned historical TREC trial corpus and matching qrels; for criterion status accuracy, use `evaluation/evaluate_agent_ablations.py` with independently prepared team/adjudicator labels. A locally run synthetic example or mocked test cannot be reported as clinical performance.

## Demo acceptance tests
- Five stages appear with **true** completion indicators.
- Official registry links are valid NCT identifiers; no synthetic fallback is mislabeled as a real trial.
- Analyst and Skeptic each issue real Ollama model calls on a manageable study; model count and duration appear.
- BBS age approval exclusion cannot be a verified triggered exclusion without an authoritative approval cutoff.
- Missing or fabricated evidence leads to unknown/clinical review; no false positive clearance.
- `Ctrl+C` ends old backend; restart after changing .env. `--check-ai` confirms the running model matches local configuration.
- Export contains no patient narrative, access token, or source criterion text.
- CI backend, frontend typecheck/build and Playwright jobs pass on the same commit.

## Poster claims and caveats
**Supported:** five-stage software workflow; criterion-level sourced reviews; independent second-model review; local inference without *per-token cloud API billing*; manual demonstration with one BBS study and two model attempts.

**Not yet measured:** clinical accuracy, criterion-level precision/recall, TREC retrieval lift, skeptic correction rate, prompt-injection attack success, speedup versus baseline. Do not convert the observed one-run counts into a research performance percentage.

## Project origin and respectful attribution
The team conceived the matching project independently before discovering a related rare/genetic-trial proposal, sought organizer clarification and received permission to proceed in its chosen track. Differentiate criterion-level evidence, independent Skeptic, planned TREC retrieval ablations and prompt-injection testing; acknowledge that proactive trial monitoring, saved alerts and family-oriented updates are complementary influences, not claims of shared ownership or an existing collaboration.
