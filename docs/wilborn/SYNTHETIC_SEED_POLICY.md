# Wilborn synthetic-only seed policy

Ranked approaches:
1. **Implemented:** bundled, version-controlled fixture with a separate hard-coded approval policy; allowlist exact fixture names; refuse external paths; insert only into the demo CaseStore; atomic insert; reject nonempty database.
2. **Next:** package integrity verification and signed release artifacts, plus read-only seed credentials and CI checks for PII-like patterns.
3. **Production separation:** independent production database and identities, deny demo-to-production network access, separate keys, audit all ingestion.
4. **Supplementary:** generative synthetic records from a constrained schema; only after independent privacy evaluation. Never train or seed from customer records by default.

The seed fixture is hand-authored fictional workflow counts, not a sample of real clients. No names, phone numbers, addresses, email addresses, or policy numbers are present.

## Usage (demo only)
```python
from wilborn_ops.store import CaseStore
from wilborn_ops.seed import seed_demo
db = CaseStore("wilborn-demo.sqlite3")
print(seed_demo(db))
db.close()
```

A fixture's metadata alone does not establish that its contents are synthetic. The approved fixture contains only service type and count. Reviewers must inspect changes to both fixture and approval policy. Production records must never be imported through this seeder.

The seeder does not grant ChatGPT production access or integrate Titan/Artex. It is an offline, synthetic-only development utility.
