# ClinicalTrial Matcher — current implementation status

## Official ClinicalTrials.gov API integration (live registry)

- **Implemented:** Official API v2 condition search and ID lookup from FastAPI; arbitrary real disease search labels through guided intake; official NCT IDs, recruitment status, eligibility descriptions, locations, URLs and update dates.
- **Implemented:** public registry version/refresh check (`GET /api/v1/registry/status`), bounded 100-candidate BM25 results, and 10-minute in-memory cache of public studies.
- **Implemented:** live follow-up questions and incremental deterministic partial reassessment use server-resolved public study criteria and official structured age restrictions. Unmapped criteria remain for expert review.
- **Implemented:** offline mocked integration tests and explicit on-machine `python run_local.py --check-live` connectivity test.
- **Validation limitation:** developer container cannot reach the live API network; GitHub CI tests are deterministic mock responses. Real endpoint tests must be executed in the user's connected local environment.
- **Safety:** Synthetic patients only; query terms and NCT IDs go to official registry, not patient answers; no eligibility guarantees, no charges.

## Milestones

- 1.5-A Guided intake: complete.
- 1.5-B Cross-trial follow-up planning: complete.
- 1.5-C Shared answer reassessment: complete.
- 1.6 Live registry integration: implemented; internet UAT required.
- Next: 1.5-D / benchmark, security and usability validation; full live AI remains optional and separate.
