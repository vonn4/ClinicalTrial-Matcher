# Architecture decisions — implementation v0.1

1. **Controlled multi-agent**: deterministic Python sequential workflow for a synthetic patient profiler, criterion assessment agent and independent skeptic. No autonomous coordination framework. Why: traceable stages, bounded API calls, independent testable responsibilities.
2. **Retrieval**: public ClinicalTrials.gov API v2 followed by pure-Python BM25. Optional Gemini embeddings reranker exists but is deliberately *off* until its TREC impact is measured; reranking cannot recover excluded candidate documents.
3. **Safety**: never treat relevance scores as eligibility; status = potential / needs information / conflict / clinician review. Any missing evidence or omitted criterion downgrades to unknown. Model disagreements require review. Complex logic needs expanded parsing and human review.
4. **Data**: official live NCT IDs cannot be confused with `DEMO-###` fixtures. No real patient data, no account service, no patient information persisted server-side.
5. **Research**: offline/replay is pre-authored synthetic demonstration, not model accuracy. Measurement routes explicitly return `not_measured` until benchmark experiments are actually performed.
6. **Budget**: free-only hosting, no managed DB, no GPU, no automatic paid upgrades; optional model calls require credentials, explicit server enablement, team token, and process-local cap.
7. **Frontend**: React/TypeScript/Vite, Recharts; custom responsive CSS initially instead of Tailwind to reduce dependencies and facilitate hackathon UI implementation. Tailwind migration remains optional.

Limitations: No verified external live connectivity in offline development environment, no npm dependency installation during initial code generation, no expert clinical validation, and no persisted trial-user collaboration. See README for status.
