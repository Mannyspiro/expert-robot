# Private registry recovery

This is bounded recovery of Merlin's canonical SQLite metadata and content-addressed blobs. It preserves the database, projects, current artifact pointers, every artifact version and its provenance, claims, relations and stored pending qualification receipts. A recovery receipt establishes only byte identity and canonical structure; it does not authenticate a signer or promote claims.

## Source contract

The caller must provide an operator-published **quiescent, non-WAL** canonical registry. Immutable read-only SQLite access is an explicit assumption, not a writer lock. Source files, SQLite sidecars, initialization, migrations and operational lock files are never modified or created by this module. A live writable registry needs a separate coordinated publication step; do not silently apply this procedure to one.

Source and destination must be absolute, disjoint, traversal-free paths with no symlink components. Destinations must not exist. Counts, sizes, filesystem entries, SQL work and elapsed time are bounded. Unsafe modes, extra/unregistered files, hard links, missing or changed blobs, noncanonical schema/lineage, failed SQLite integrity/foreign-key checks and altered manifests are rejected.

## API

`dot_ai_os.recovery` exposes `SnapshotBounds`, `create_snapshot`, `verify_snapshot` and `restore_snapshot`. A snapshot contains `manifest.json` plus `registry/merlin.sqlite3` and all registered blobs. The independently retained expected manifest SHA-256 is required for verification and restoration; computing a new expected hash from an untrusted snapshot defeats that identity check.

```python
from pathlib import Path
from dot_ai_os.recovery import (
    SnapshotBounds, create_snapshot, verify_snapshot, restore_snapshot,
)

bounds = SnapshotBounds(max_db_bytes=4 * 1024 * 1024,
                        max_total_bytes=16 * 1024 * 1024)
receipt = create_snapshot(Path('/published/registry'),
                          Path('/private-backups/snapshot-001'), bounds)
pin = receipt['manifest_sha256']  # Retain separately in a trusted run record.
verify_snapshot(Path('/private-backups/snapshot-001'), pin, bounds)
restore_snapshot(Path('/private-backups/snapshot-001'),
                 Path('/isolated/restored-registry'), pin, bounds)
```

Payload files use explicit 0600 modes and directories 0700. Linux atomic rename-noreplace publishes only a fully checked new target. Failures retain a quarantined staging directory and never overwrite an existing destination. Canonical metadata is compared before and after SQLite online backup, and source identities are rechecked. Resource bounds and before/after checks do not eliminate the quiescent-source prerequisite.

## Operational drill

The fixed OCI `recovery_drill` profile validates the exact private v2 release/config/unit and the two synthetic engineering records. It creates a unique workspace under `/var/lib/merlin-dot-private-recovery-drills/`, executes recovery as the actual service UID 982, starts an isolated Unix-socket runtime on the restored registry, checks source/history/provenance identity and tools, rejects separate changed/missing-blob fixtures, then terminates only its child server. It compares production PID, release/config/unit, state-file identities and health before and after. It never stops production, switches its paths or reboots the shared runner.

The snapshot and receipt remain in the unique private workspace. GitHub artifacts contain compact evidence, not the source registry payload. A same-host snapshot is not an off-host disaster-recovery backup. This drill covers the small synthetic private runtime; the full project corpus, other canonical stores/workers, deployment/reboot recovery, independent qualification and separately authorized off-host retention remain distinct gates.

## Verification

Run the focused recovery suite with `PYTHONPATH=python python -m unittest discover -s tests -p test_recovery.py -v`. The fixed OCI profile additionally runs the existing runtime tests and nine orchestration tests, requiring zero skips. Test counts and exact live run receipts belong in the master plan and evidence checkpoint, never inferred from this document.
