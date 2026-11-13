# Merlin canonical artifact version lineage v1

**Status:** implemented on the artifact-version feature branch; hosted validation pending. This contract is not a production acceptance record.

## Existing canonical ownership

The existing `MerlinRegistry` remains the sole owner of project artifact identity and content-addressed bytes. The existing `project_artifacts` relation remains the current-path projection for compatibility. This change does not introduce a second registry, artifact service, or source of truth.

## Version model

Each `(project_id, logical_path)` has a monotonically increasing sequence in `artifact_versions`:

- `version`: positive integer, scoped to the project and logical path.
- `digest`: SHA-256 identity of the exact immutable blob.
- `media_type` and `size_bytes`: properties of that version.
- `previous_digest`: prior current version's digest, or null for the first version.
- `created_at`: registry insertion time.

The current `project_artifacts` pointer remains a compatibility projection. It may move to the latest version, but the version ledger is append-only and protected by SQLite update/delete triggers.

## Write semantics

1. Validate project identity, relative logical path, byte content and media type.
2. Hash exact bytes and store them under the SHA-256 content-addressed blob path.
3. Verify an existing blob before reuse; never silently overwrite a digest path whose bytes disagree.
4. Under a SQLite immediate transaction, insert the blob metadata if absent.
5. If the requested digest is already current at the logical path, treat the write as an idempotent replay.
6. Otherwise append the next version, linking it to the previous digest, then update the current-path projection in the same transaction.

Reverting to bytes used by an older version creates a new version with the old digest and the immediately previous digest as its parent. This preserves chronology without duplicating blob storage.

## Migration and reads

Existing `project_artifacts` rows are backfilled as version 1 when the new table is initialized. `artifact_history(project_id, logical_path)` returns the ordered immutable history. Project inventory continues to return the current digest and additionally reports its current version number.

## Evidence boundary

A version record proves what bytes the registry stored and in what sequence. It does not prove scientific correctness, formal validity, execution provenance, CACE verification, signature validity, approval or deployment. Those remain separate typed records and gates.

## Regression requirements

- first write creates version 1;
- changed bytes create the next version;
- replay of the current bytes does not create a duplicate version;
- reverting to earlier bytes creates a new chronological version;
- prior digest links are correct;
- update/delete attempts on version rows fail;
- existing databases backfill current artifacts as version 1;
- unknown projects and traversal paths fail closed;
- current inventory agrees with the latest version record.

## Next integration steps

1. Run the focused registry tests and the full unified Merlin CI suite on the exact branch head.
2. Add lineage-event linkage for artifact versions without duplicating the existing graph or outbox.
3. Bind execution results and CACE receipts to exact `(project_id, logical_path, version, digest)` references.
4. Expose history through the existing read-only query facade and API.
5. Add backup/restore and concurrent-writer tests before multi-host deployment.
