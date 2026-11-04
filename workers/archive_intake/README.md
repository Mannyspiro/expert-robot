# Merlin Safe Archive Intake v1

A standard-library-only Python worker that safely inspects ZIP packages, extracts regular files into a staged directory, hashes each extracted file, classifies common research and engineering formats, and writes an inventory manifest.

## Run

Python 3.10+:

    python3 workers/archive_intake/merlin_archive_intake.py package.zip --output ./intake/package

Run tests from the repository root:

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

## Output

merlin-intake-manifest.json contains the archive digest, intake ID, policy limits, timestamps, file count, uncompressed byte total, and sorted per-file inventory with digest, size, and coarse classification.

The manifest is an intake record, not a trust verdict. Files remain untrusted inputs and require format-specific parsers and independent verification before use.

## Current limitations

- ZIP only; TAR, 7z, RAR and disk images are unsupported.
- Classification is extension-based, not content validation.
- This worker does not write to GitHub, invoke Avrea, call CACE, or register projects in Hermes.
- The caller must sandbox the worker process and apply OS-level CPU and storage quotas.
