# Wilborn & Associates Ltd. — Merlin Business Operations MVP

Status: prototype, not deployed or production qualified.

## Scope
A PII-free, in-memory workflow for document signing, insurance quote requests, workshops and general services. Intake -> scheduled -> in service -> completed -> follow-up -> closed. Invalid transitions fail closed. Completion and closure require explicit human approval. Event hash chains detect accidental or unsophisticated modification but are not authentication or encryption.

## Merlin research and build loop
Observe business requirement; state hypothesis and acceptance criteria; propose minimal implementation; test positive and negative fixtures; independently review evidence; update plan. Never silently promote, deploy, contact clients or expand authority.

## Production gates
1. Confirm business roles, service permissions, client consent, record retention and regulatory scope.
2. Add durable database, migrations, RBAC, authentication, tenant isolation, backups and recovery tests.
3. Add privacy-reviewed intake and scheduling adapters with idempotency.
4. Add accessible mobile web UI and staff dashboards.
5. Run isolated tests and independent end-to-end qualification; obtain approval before a real-client pilot.

## Verification
Run `python -m unittest discover -s tests -p test_wilborn_workflow.py`. Tests do not qualify production.

## Research lenses
Simplex: not applicable to discrete stage transition. N-ality: role, service, stage remain separate dimensions. Continuum: defer until time-to-service measurements. Fuzzy: forbidden for authorization; permission is Boolean.
