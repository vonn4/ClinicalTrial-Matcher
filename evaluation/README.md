# Scientific evaluation (no fabricated findings)

Three distinct evaluation programs:

1. **TREC retrieval:** Run against the exact historical TREC Clinical Trials corpus and its matching judgment file, **not today's live registry**. Calculate nDCG@10, P@10, and eligible Recall@10 using the supplied evaluation script and record model/ranker versions.
2. **Criterion-level accuracy:** Label synthetic cases independently and explicitly; measure status confusion matrix, omitted criteria, missed exclusions, and abstentions. Team-generated labels are not clinical expert ground truth.
3. **Prompt injection / skepticism:** Run clean and manipulated study-description variants on matched synthetic profiles. Compare first agent, skeptic, and evidence-validated outputs. Report both corrections and regressions.

Do NOT imply benchmark runs have already been performed. Results and figures are produced only from test run files; sample screenshots and replay fixtures are not quantitative research evidence.

## Retrieval input files
Prepare two CSV files:

- `qrels.csv`: `query_id,nct_id,grade` (`grade`: 0=nonrelevant, 1=excluded, 2=eligible).
- `ranking.csv`: `method,query_id,nct_id,rank` (1-based rank; one row per retrieved study).

Then:

```bash
python evaluation/evaluate_retrieval.py --qrels path/to/qrels.csv --ranking path/to/ranking.csv --out evaluation/results/retrieval_results.json
```

The script prints actual measured results and writes a machine-readable file. Results are intentionally not checked into the source repository without review.

## MVP 2.0: five-agent ablation scorer

The offline CLI `evaluation/evaluate_agent_ablations.py` consumes two **actual, separately prepared** CSVs and writes results with method comparisons; it does not create ground-truth labels or simulate agent outputs.

- Labels: `case_id,nct_id,criterion_id,kind,gold_status`, where `kind` is inclusion/exclusion and statuses are met/not_met/unknown/clinical_review.
- Predictions: `method,case_id,nct_id,criterion_id,status`; methods should include deterministic, analyst, analyst+skeptic, and full-five-agent where available.

Example:

```bash
python evaluation/evaluate_agent_ablations.py --labels evaluation/data/labels.csv --predictions evaluation/data/predictions.csv --out evaluation/results/agent_ablation_results.json
```

Unreported predictions count as unknown rather than disappearing from denominators. Metrics include exact-status accuracy, decisive coverage, abstention, exclusion-trigger recall, unsafe exclusion clearances and a status confusion table. Report the labels' provenance: team-generated labels must not be described as clinical expert ground truth.


## Local Qwen3/Ollama reproducible evidence (2026-11-10)

**A successful browser trace is one demonstration, not an accuracy estimate.** The initial fictional Bardet-Biedl syndrome run showed five stages, two model stages, two model attempts and one official study. The new stage-progress UI reports actual running stages and allows export of **anonymized timing evidence** after completion.

After each actual model-assisted run, use the **Export anonymous timing evidence** button. It saves `clinicaltrial-matcher-run-metrics.json` containing only stage times, counts, public NCT IDs and assessment summary categories. Never upload a real patient profile or `.env`. Gather at least five comparable runs before interpreting median/p95 as stable.

To summarize exported measurements:

```powershell
python evaluation/summarize_local_runs.py "C:\path\to\clinicaltrial-matcher-run-metrics.json"
```

To run *synthetic* indirect-injection probes against local Ollama:

```powershell
python evaluation/security_tests/run_local_probes.py --dry-run
python evaluation/security_tests/run_local_probes.py --model qwen3:4b --include-skeptic
```

The real probe sends only fictional text and uses localhost Ollama; it takes 2 calls (or 4 with `--include-skeptic`). It records marker emission and evidence validation, **not** a validated broad prompt-injection success rate. The dry run never sends requests.

Existing `evaluate_agent_ablations.py` and `evaluate_retrieval.py` require actual labels/rankings before they can produce empirical claims. Do not substitute mocked CI outputs for real labels or TREC measurements.
