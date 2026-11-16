# Merlin media worker adapter contract

**Status:** implemented as isolated Python adapters; not registered as a configured or qualified production capability.

## Trust and execution boundary

- ComfyUI is reached only through an HTTP loopback endpoint. The adapter submits one bounded workflow, polls the job, retrieves outputs through the ComfyUI view endpoint, and records exact output byte digests.
- Blender is launched as an absolute executable using an argument vector and `shell=False`. Scene and output paths must remain inside a configured workspace. The worker is headless, uses a bounded frame and fixed low-resolution preflight settings, and enforces a process deadline.
- Both adapters emit `merlin-media-execution/1` receipts with input digest, output digest(s), timing, logs, and resource/telemetry limitations. These are execution receipts only; they do not establish CACE verification, source qualification, or promotion authority.
- No endpoint is exposed publicly. No model weights are downloaded. No adapter is invoked by the Merlin HTTP process.

## Current limitations

- The ComfyUI adapter uses `/prompt`, `/api/jobs/{id}`, `/api/jobs/{id}/cancel`, and `/view`. Its job-output parser follows the inspected 0.45.0 source shape (node-keyed output groups such as `images`). It must still be integration-tested against a pinned upstream commit before use.
- Blender's adapter has not been run against the uploaded binary. It performs a bounded `--version` probe and includes the returned version string when available; the executable digest still needs to be recorded in the later registry-backed qualification receipt.
- Output files are written to the caller-provided workspace. ComfyUI output count and aggregate bytes are capped; Blender output bytes and execution time are capped. Registry persistence and append-only artifact provenance integration are a separate gate.
- The adapters are not yet wired into `/api`, Hermes, MCFC leases, or the capability registry. Existing `media.image` and `media.video` states remain unavailable/unqualified.

## Preflight acceptance

1. Pin ComfyUI upstream commit and dependencies; record archive/source digests.
2. Run the deterministic built-in workflow on a qualified Linux x86-64 worker and verify queue, poll, cancel, output retrieval, and receipt digests.
3. Run Blender `--version` and one tiny CPU scene on a qualified Linux x86-64 worker; record executable digest, version, arguments, scene digest, output digest, exit status, runtime and host telemetry.
4. Add canonical registry artifact persistence and CACE/domain verification only after successful execution tests.
