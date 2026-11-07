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
