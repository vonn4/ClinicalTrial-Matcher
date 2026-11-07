# MVP 1.5 — Adaptive Intake and Shared Cross-Trial Clarification

## Status and scope

This project builds in reviewable increments, keeping the initial demo available.
All input and test records must be **fictional**. It does not determine medical eligibility.

### Increment A (implemented): guided baseline intake

- A free-text description is optional. Users can select a fictional condition and answer structured questions.
- Disease-specific questions appear only for relevant conditions. The backend independently validates applicability.
- Every question is either unanswered, explicitly answered, unknown, pending, not tested, not applicable, or declined.
- A structured answer with an explicit value is different from a mentioned but unverified test name.
- Prior and current treatments are separate. Stage is asked only for represented cancer categories.
- The patient reviews answers before trial discovery. Correcting inputs and resubmitting rebuilds the profile.
- Backend reconstruction prevents forged derived fields from being trusted in synthetic replay.
- The original free-text mode and static lung-cancer teaching example remain functional.
- Guided profiles have **no eligibility judgments** yet. They only retrieve candidate fictional studies in sandbox mode.

### Increment B (next): criterion-to-fact mappings and follow-up queue

- Preserve the original trial requirement text and stable source reference.
- Map supported inclusion/exclusion criteria to typed fact identifiers.
- Determine which facts are missing per trial, marking unmappable criteria for clinical review.
- Generate grounded, editable questions with explanatory source links.
- Do not ask speculative or unsupported questions from an LLM.

### Increment C: deduplication and incremental reassessment

- One canonical patient fact registry powers all studies.
- Deduplicate only semantically equivalent questions with the same fact key and answer requirements.
- For example, whether testing occurred and whether a specific variant was found are distinct facts.
- Each answer updates all dependent criterion evaluations while preserving differing thresholds.
- Invalidated or contradicted facts revoke earlier preliminary judgments.
- Newly answered facts never automatically certify eligibility.

### Increment D: measured UX and safety tests

- Automate an end-to-end intake → trial discovery → targeted questions → refresh scenario.
- Measure how many duplicate questions are eliminated and how many criteria remain unknown.
- Evaluate corrections, skip states, stale facts, source-evidence errors, unsupported conditions, and injection attempts.
- Only experimental results from actual test runs appear in the research dashboard/poster.

## Backend contracts implemented in increment A

`GET /api/v1/intake/questions?condition=non-small%20cell%20lung%20cancer` returns the applicable question bank.

`GET /api/v1/intake/questions?include_all=true` returns all questions for frontend conditional display.

`POST /api/v1/intake/profile` takes an `IntakeSubmission`:

```json
{
  "synthetic": true,
  "narrative": "Optional fictional story for human review",
  "answers": {
    "condition": {"state": "answered", "value": "non-small cell lung cancer"},
    "age": {"state": "answered", "value": "42"},
    "egfr_result": {"state": "pending", "value": null}
  }
}
```

The resulting `PatientProfile` contains `intake_answers` as canonical values,
`intake_story` as unverified narrative, and user-visible `facts` with source labels.
Legacy endpoints remain backward-compatible.

## Team implementation checkpoints

For every increment: run `python -m pytest -q backend/tests`, check frontend `npm run build`,
run `python run_local.py --check` after starting the launcher, and verify GitHub Actions.
Do not merge until CI is green and the preview is checked manually in a browser.
