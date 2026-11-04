# Merlin Safe Archive Intake v1

A standard-library-only Python worker that safely inspects ZIP packages, extracts regular files into a staged directory, hashes each extracted file, classifies common research and engineering formats, and writes an inventory manifest.

## Run intake

Python 3.10+:

    python3 workers/archive_intake/merlin_archive_intake.py package.zip --output ./intake/package

## Register inventory

    python3 workers/archive_intake/register_inventory.py ./intake/package/merlin-intake-manifest.json --database ./data/merlin-registry.sqlite3

## Run tests

    python3 -m unittest discover -s workers/archive_intake/tests -v

No third-party dependencies are required.

## Safety behavior

- Never executes, imports, previews, or opens extracted content in an application.
- Rejects absolute paths, parent traversal, duplicate normalized paths, symlinks, special filesystem entries, encrypted members, excessive file counts, oversized members, oversized total expansion, and suspicious compression ratios.
- Validates archive metadata before extraction.
- Streams members while enforcing actual expanded-size limits.
- Extracts into a staging directory and promotes it only after successful completion.
- Refuses to overwrite an existing destination.
- Writes SHA-256 hashes for the archive and every extracted file.
- Failed intake removes staging files and returns a quarantined status.

## Registry behavior

The separate SQLite adapter validates manifest structure and digest relationships, stores one intake record plus per-file artifact rows, and is idempotent for an identical manifest. Reusing an intake ID with a different manifest digest is rejected. This is a local inventory adapter, not yet the canonical multi-user Merlin registry service.

## Output and limitations

The manifest records archive digest, intake ID, policy limits, timestamps, file count, uncompressed byte total, and sorted per-file inventory. Extension-based classification is descriptive, not a trust verdict.

ZIP only; TAR, 7z, RAR and disk images are unsupported. This worker does not write to GitHub, invoke Avrea, call CACE, or register projects in Hermes. The caller must sandbox the worker process and apply OS-level CPU and storage quotas.
