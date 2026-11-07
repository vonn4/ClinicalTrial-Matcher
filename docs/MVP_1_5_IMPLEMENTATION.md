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
- Guided profiles initially retrieve candidate fictional studies. Increment C adds bounded rule-based criterion reviews; **not independent AI assessments or clinical eligibility decisions**.

### Increment B (implemented): criterion-to-fact mappings and follow-up queue

- Preserve the original trial requirement text and stable source reference.
- Map supported inclusion/exclusion criteria to typed fact identifiers.
- Determine which facts are missing per trial, marking unmappable criteria for clinical review.
- Generate grounded, editable questions with explanatory source links.
- Do not ask speculative or unsupported questions from an LLM.

### Increment C (implemented in review): shared answers and incremental reassessment

- One canonical patient fact registry powers all studies; corrections are preserved separately from the optional patient story.
- Deduplicate only semantically equivalent questions with the same fact key and answer requirements.
- For example, whether testing occurred and whether a specific variant was found are distinct facts.
- Each answer updates all dependent criterion evaluations while preserving differing thresholds.
- Invalidated or contradicted facts revoke earlier preliminary judgments; linked criteria are recalculated from their original source text.
- Newly answered facts never automatically certify eligibility. Full coverage without independent review remains `clinical_review`.

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

## Increment 1.5-B — source-grounded shared question planning

- `backend/app/followups.py` contains a conservative allowlist of recognized
  trial criterion phrasings. A criterion maps to a canonical fact key only
  when the source text is supported and verified verbatim against the study.
- `POST /api/v1/intake/followups` accepts a profile, mode, and 1–8 trial IDs.
  Sandbox IDs resolve against server-owned fictional fixtures; NCT IDs are
  re-fetched from the official public registry. The browser cannot supply
  arbitrary criterion strings or claim clinical interpretations.
- One question groups *exact* criterion references across distinct trials;
  matching age thresholds remain distinct in their own original source text.
- `answer_state` can distinguish missing, unknown, pending, not tested,
  declined, and not applicable; completed explicit facts are not repeatedly
  requested. A generic positive EGFR result still prompts for activating
  variant specificity.
- Unmapped requirements are reported, not treated as negative or satisfied.
- UI is a **read-only question-planning preview** until 1.5-C. No eligibility
  verdict, answer propagation, or medical screening is implied.
- Acceptance scenario: guided NSCLC with age unknown → one age question
  linking three studies; EGFR pending → a distinct pending-status question;
  opening Why are we asking? shows trial-specific verbatim criteria.

## Increment 1.5-C — concrete API and interaction contract

`POST /api/v1/intake/reassess` accepts a `ReassessmentRequest`: the current
**synthetic** patient profile, 1–8 known study identifiers, mode (`replay` or
`live`), and a bounded dictionary of new answer states keyed by the canonical
fact identifier. Only keys already linked to retrieved, server-fetched criteria
can be updated. The request cannot supply its own eligibility criteria.

Example (fictional lung cancer baseline with unknown age):

```json
{
  "mode":"replay",
  "trial_ids":["DEMO-001","DEMO-002","DEMO-003"],
  "profile":{"description":"Synthetic guided patient profile ...", "synthetic":true,
    "intake_answers":{"condition":{"state":"answered","value":"non-small cell lung cancer"},
    "age":{"state":"unknown","value":null}}},
  "updates":{"age":{"state":"answered","value":"42"}}
}
```

Response: rebuilt canonical patient profile; independent rule-based criterion
reviews for each study; suggested **remaining** shared questions; a list of
previously answered questions that can be edited; and `changed_criteria`
records for every status that changed after the answer.

We do **not** assume all trial criteria are parseable. Unsupported and complex
rules remain `clinical_review`; an unmeasured AI skeptic is never fabricated.
A positive EGFR result still requires variant clarification and expert review.
Corrections from 42 to 16 or from an answer back to unknown are reflected
across every linked age criterion, while each study maintains its own age limit.

### Manual test scenario

1. Run `python run_local.py` and open `http://localhost:5173`.
2. Select Guided intake / Interactive sandbox; choose NSCLC and mark age unknown.
3. Complete the profile and discover DEMO-001/002/003.
4. Find the **one age question** labeled **3 trials** and answer **42**.
5. Confirm three age criteria change from unknown to met; exclusions stay separate.
6. Use **Edit** next to the applied age answer; change it to **16**.
7. Confirm three age criteria change to *not met*, without any eligibility pass.
8. Mark EGFR pending and confirm it is not treated as a negative result.
9. Open the trial evidence pane; it must state that no independent AI skeptic
   or clinical screening has taken place.

`run_local.py --check` now includes a live HTTP smoke test for one-answer-to-
three-criteria reassessment. Automated backend tests cover corrections,
invalid answers, mismatched IDs, EGFR ambiguity, and contradictory treatment
history. Actual frontend production build remains a separate GitHub CI gate.

## Release status and next increment

A and B are under draft review. C is an additional draft increment; merge only
after browser review. D still covers real browser automation, usability
measurements, and safety evaluation. No real patient data or paid services.
