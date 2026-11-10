# Poster and technical report plan

## Research figures (only measured results)
1. System architecture and evidence traceability diagram.
2. BM25 vs hybrid RAG on *matching historical* TREC corpus: nDCG@10 and eligible Recall@K. Include dataset identifiers and sample sizes.
3. Criterion-level classification confusion matrix using labeled synthetic cases; describe limitations of those labels.
4. Primary assessor vs independent skeptic: missed exclusions, corrections, regressions, and disagreement rate. Evaluate on identical test cases.
5. Indirect prompt-injection attacks against trial-text inputs: attack success / abstention with and without safeguards, controlled clean baselines.
6. Per-stage latency and request volume from actual recorded runs.

Until experiments run, present "not measured" rather than fabricated placeholders.

## Independent development / respectful competition
The team independently conceived ClinicalTrial Matcher before noticing a related rare/genetic disease navigation proposal. The team sought clarification and was explicitly permitted by organizers to proceed in its registered track. Our distinguishing technical emphasis is criterion-level evidence-anchored assessment, independently formed skeptic review, TREC retrieval baselines, and prompt-injection defense testing. The other proposal's proactive monitoring, caregiver-centered framing and clinician handoff are complementary; we respectfully acknowledge their influence on our extensions and see potential for future collaboration. Never imply an existing collaboration or ownership over a generic idea.

## Report required sections
Abstract; introduction and unmet need; original contributions; related project context; functional requirements; architecture; retrieval; eligibility; skeptic; dashboard; security; methods; datasets; measured results; error analysis; uncertainty and clinical limitations; cost/hosting; accessibility; future collaboration; reproducibility; references.


## November 10 local Ollama working build and improvement branch

Working demonstration branch `feat/ollama-local-agents` remains unchanged. Improvement branch `feat/ollama-performance-evaluation-poster` adds true stage-progress polling, one-study CPU-friendly default, de-identified stage-metrics export, age-threshold contradiction checks, synthetic-only prompt-injection probes, and offline automated regression tests.

Poster-ready observation (single fictional BBS run, **not an accuracy benchmark**): five completed stages; two AI-assisted stages; two model attempts; one official recruiting study `NCT07674290`. The observed treatment-age exclusion was questionable, and the improved branch now downgrades approval-age judgments requiring a missing regulatory cutoff to manual clinical review. **Do not** say this fixes all eligibility errors or cite an accuracy improvement without real repeated labeled evaluations.

Full documentation: [Ollama evidence and acceptance plan](OLLAMA_2026-11-10_RELEASE_AND_POSTER_EVIDENCE.md).
