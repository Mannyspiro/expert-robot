# Merlin Safe Archive Intake and Local Registry

A standard-library-only Python prototype for non-executing ZIP intake and local SQLite inventory registration.

## Intake

    python3 workers/archive_intake/merlin_archive_intake.py package.zip --output ./intake/package

## Register

    python3 workers/archive_intake/register_inventory.py ./intake/package/merlin-intake-manifest.json --database ./data/merlin-registry.sqlite3

## Tests

    python3 -m unittest discover -s workers/archive_intake/tests -v

Python 3.10+; no third-party dependencies. Tests are authored but must be run in a controlled environment before this PR can leave draft status.

## Trust boundaries

- Archive contents are never executed, imported, rendered, or opened in an application.
- Intake rejects absolute paths, traversal, duplicate normalized paths, symlinks, special filesystem entries, encrypted members, oversized entries, excessive expansion, and suspicious compression ratios.
- Extraction streams data into a staging directory and promotes it only after complete success.
- The registry independently validates manifest paths and metadata; it does not trust the intake worker merely because it produced the manifest.
- Hashes establish byte identity, not safety, authorship, correctness, or provenance.
- Extension-based classifications are hints, not trust verdicts.
- Callers must sandbox the process and impose OS-level CPU, memory, and disk quotas.

## Integration status

The Hermes event adapter emits a deterministic local event envelope; it does not call Hermes. Avrea and CACE contracts define future handoff payloads only; no Avrea job is dispatched and no CACE proof is claimed. GitHub provenance fields are optional metadata and must be populated from a verified repository/commit response by a future adapter.

ZIP only; TAR, 7z, RAR, disk images, and remote URLs are unsupported. SQLite is a single-host prototype, not a canonical multi-user registry service. Do not expose this database directly as a network API.
