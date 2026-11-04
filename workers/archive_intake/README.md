# Merlin Safe Archive Intake and Registry Contracts v1

A standard-library-only Python prototype for non-executing ZIP intake, local SQLite inventory registration, and deterministic Hermes-compatible event creation. JSON Schemas define the next integration boundaries for Avrea, CACE, and CAD/MCFC artifacts.

## Intake and register

    python3 workers/archive_intake/merlin_archive_intake.py package.zip --output ./intake/package
    python3 workers/archive_intake/register_inventory.py ./intake/package/merlin-intake-manifest.json --database ./data/merlin-registry.sqlite3

## Create a Hermes outbox event

    python3 workers/archive_intake/hermes_event.py ./intake/package/merlin-intake-manifest.json --project-id PROJECT_ID --outbox ./data/hermes-outbox/event.json

Optional Git provenance must be supplied as a pair using `--repository owner/name --commit-sha FULL_40_CHAR_SHA`. The adapter validates the SHA shape but does not independently fetch GitHub; a future GitHub adapter must fetch the commit and bind the returned canonical SHA/URL before attaching provenance. The outbox event is local only; no Hermes network call occurs.

## Export the project provenance graph

    python3 workers/archive_intake/project_graph.py ./intake/package/merlin-intake-manifest.json --project-id PROJECT_ID --out ./data/project-graph.json

The graph links project, intake, artifact occurrence, content hash, and optional Git commit nodes. It is a deterministic local JSON export, not a connected graph database. Git provenance remains optional and must come from a separately verified GitHub commit fetch.

## Tests

    python3 -m unittest discover -s workers/archive_intake/tests -v

Python 3.10+; no third-party dependencies. Tests are authored but have not yet been executed in this environment. Do not remove draft status until they pass in a controlled environment.

## Contracts

- `schemas/intake-manifest-v1.schema.json`: archive and file inventory envelope.
- `contracts/merlin-integration-contracts-v1.json`: project registry, Hermes, GitHub provenance, Avrea, CACE, and CAD/MCFC integration rules.
- `schemas/avrea-task-contract-v1.schema.json`: explicit approval, capability allowlist, resource budgets, bounded task and required result manifest.
- `schemas/cace-verification-receipt-v1.schema.json`: subject hash, verifier/toolchain identity, assumptions, axioms, result and log hash.
- `schemas/cad-mcfc-artifact-metadata-v1.schema.json`: units, coordinate frame, revision, source hash and derived-artifact provenance.

## Trust and authority boundaries

- Archive contents are never executed, imported, rendered, or opened in an application.
- Intake rejects absolute paths, traversal, duplicate normalized paths, symlinks, special filesystem entries, encrypted members, oversized entries, excessive expansion, and suspicious compression ratios.
- Extraction streams data into a staging directory and enforces both per-member and cumulative actual-byte limits.
- The registry independently validates manifest paths and metadata; it does not trust the intake worker merely because it produced the manifest.
- Hashes establish byte identity, not safety, authorship, correctness, or provenance.
- Extension-based classifications are hints, not trust verdicts.
- Avrea dispatch remains proposed until a separately recorded approval is supplied; this repository currently has no Avrea dispatcher.
- CACE receipts are a schema only; no proof or verification is claimed by this PR.
- CAD/MCFC metadata is a schema only; no CAD geometry or solver execution is implemented here.
- Callers must sandbox the process and impose OS-level CPU, memory, and disk quotas.

## Limitations and status

ZIP only; TAR, 7z, RAR, disk images, and remote URLs are unsupported. SQLite is a single-host prototype, not a canonical multi-user registry service. The Hermes adapter creates a deterministic local event envelope, not a live Hermes integration. No CI workflow was added, to conserve GitHub Actions quota. No Avrea, CACE, or external CAD service was invoked.
