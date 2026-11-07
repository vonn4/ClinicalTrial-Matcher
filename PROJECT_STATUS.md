# ClinicalTrial Matcher — status (MVP 1.5-C)

**Development branch:** `feat/mvp-1.5-shared-reassessment`, based on `feat/mvp-1.5-trial-followups`.

- [x] 1.5-A — guided baseline questionnaire, disease-specific branches, profile editing, explicit unknown/pending/not-tested states.
- [x] 1.5-B — conservative criterion-to-fact map, one deduplicated question across multiple trials, source evidence, unmapped criteria warnings.
- [x] 1.5-C — answers and corrections for shared questions, one canonical synthetic patient profile, rule-based re-evaluation against each linked trial criterion, answer-editing UI, criterion status-change feedback.
- [ ] 1.5-D — automated browser E2E, usability/question-burden measurement, real registry validation and richer UX.
- [ ] MVP 2/3 — empirically validated Gemini eligibility and independent skeptic agents.
- [ ] TREC benchmark and prompt-injection experiments; no metrics may be fabricated.

**Safety and limitations:** Self-reported fictional data only, no medical advice, no confirmed eligibility, no real patient records. Deterministic reviews only support a small allowlist of criteria; unsupported requirements remain clinical review. The independent skeptic is not run in the rule-based workflow. Original fixed replay and optional live model mode remain separate. Nothing requires a paid API.

**Verification:** Local backend regression suite has 56 tests passing (including 10 added reassessment checks); launcher syntax compiled, frontend TS/TSX syntax parsed. GitHub CI must verify full TypeScript production build on this branch before merging.

See `docs/MVP_1_5_IMPLEMENTATION.md` for technical scope, API contract and UAT.
