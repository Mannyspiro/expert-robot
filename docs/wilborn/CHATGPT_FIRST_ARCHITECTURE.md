# ChatGPT-first Wilborn business operations — implementation contract

User experience: ChatGPT is the conversational front door; Merlin is a bounded research/coding/analysis worker; a separately protected business database is the system of record.

## Current working scope
- PII-free local case workflow with SQLite persistence and CLI.
- No deployed endpoint, ChatGPT custom connector, authentication or live Merlin invocation yet.
- Run locally: `python -m wilborn_ops.cli --db /tmp/wilborn-demo.sqlite3 create workshop`
- Then `python -m wilborn_ops.cli --db /tmp/wilborn-demo.sqlite3 list`.
- Tests: `python -m unittest discover -s tests -p 'test_wilborn_*.py'`.

## Intended chat operations
- List upcoming appointments and missing intake requirements.
- Create client referrals and staff tasks with confirmed permissions.
- Prepare, but do not automatically send, follow-up communications.
- Ask Merlin to research service improvements and propose tested changes.

## Integration boundary
A future authenticated, audited HTTPS service must expose explicit read/write business operations to a ChatGPT-compatible connector. The connector must use scoped service identities, least privilege, consent, rate limits, replay protection, approval gates, and redaction. Merlin is never given unrestricted direct database or secrets access. Do not expose the local CLI or SQLite file to the internet.

## Qualification gates
1. Independently execute tests and verify crash/restart durability.
2. Implement authentication and authorization before any network API.
3. Add migrations, backup/restore, concurrency control, encryption, monitoring and data retention.
4. Add real business records only after privacy review and approval.
5. Deploy and test an actual ChatGPT connector before claiming conversational access.

No public repository may contain customer PII, tokens or secrets.
