# Merlin archive intake, canonical registry and integration adapters

Standard-library Python prototype for non-executing ZIP intake, canonical local inventory, read-only project/artifact queries, GitHub commit receipts, Hermes outbox lifecycle, fail-closed Avrea task approvals, CACE CLI verification receipts, research graph export and CAD/MCFC metadata.

Python 3.10+ for the Merlin modules. CACE's own current quickstart specifies Python 3.11+ and its pinned dependencies for CACE execution.

## 1. Intake and register

    python3 workers/archive_intake/merlin_archive_intake.py package.zip --output ./intake/package
    python3 workers/archive_intake/register_inventory.py ./intake/package/merlin-intake-manifest.json --database ./data/merlin.sqlite3

## 2. Canonical registry and read-only API

Initialize and register a project:

    python3 workers/archive_intake/canonical_registry.py init --database ./data/merlin.sqlite3
    python3 workers/archive_intake/canonical_registry.py create-project merlin-main "Merlin" --database ./data/merlin.sqlite3
    python3 workers/archive_intake/canonical_registry.py attach-intake merlin-main sha256:ARCHIVE_SHA --database ./data/merlin.sqlite3

Start the read-only API (loopback by default):

    python3 workers/archive_intake/canonical_registry.py serve --database ./data/merlin.sqlite3 --host 127.0.0.1 --port 8765

Read endpoints:
- `GET /health`
- `GET /v1/projects?limit=100&offset=0`
- `GET /v1/projects/{project_id}`
- `GET /v1/projects/{project_id}?view=artifacts&classification=source_code`
- `GET /v1/artifacts/{sha256}` (occurrences and verification receipts)

HTTP mutations are deliberately disabled. Non-loopback binding requires `MERLIN_REGISTRY_READ_TOKEN`; when set, every GET must include `Authorization: Bearer <token>`. The API is read-only; project creation, intake attachment and evidence writes use local service adapters.

## 3. Verified GitHub commit receipt

    GITHUB_TOKEN=... python3 workers/archive_intake/github_commit_receipt.py OWNER/REPO FULL_40_CHAR_SHA --project-id merlin-main --database ./data/merlin.sqlite3 --require-signed

The adapter fetches the commit from GitHub's REST API, checks that GitHub returns the exact requested full SHA, records the canonical commit URL, hashes the API response and stores GitHub's signature-verification result. `--require-signed` rejects commits GitHub does not report as signature-verified. A successful API fetch establishes what GitHub returned at retrieval time; it is not a cryptographic proof of the source tree's safety or correctness.

## 4. Hermes outbox lifecycle

Create the deterministic event envelope:

    python3 workers/archive_intake/hermes_event.py ./intake/package/merlin-intake-manifest.json --project-id merlin-main --outbox ./data/hermes-outbox/event.json

Enqueue it:

    python3 workers/archive_intake/hermes_outbox.py enqueue ./data/hermes-outbox/event.json --database ./data/merlin.sqlite3

The outbox supports lease, retry and acknowledgement. Acknowledgements must accept the exact event ID and be returned by the worker that owns the lease. `HermesTransport` is the integration interface for a real Hermes client. No Hermes endpoint or credentials are configured here, so this PR does not claim live event delivery.

## 5. Avrea approval and dispatch gate

A task must be bound to a canonical approval record, a capability allowlist, resource maxima, timeout and a result manifest. Record an operator approval:

    python3 workers/archive_intake/avrea_dispatch.py record-approval approval.json --database ./data/merlin.sqlite3

Then submit:

    python3 workers/archive_intake/avrea_dispatch.py submit task.json --approval approval.json --policy avrea-policy.json --database ./data/merlin.sqlite3

Without a configured Avrea provider, the task remains `approved_waiting_for_provider`; it is not executed. A provider adapter must implement submit/result retrieval and return a result manifest. This repository currently has no Avrea connector or provider credentials, so no Avrea job has been dispatched. Approval records are operator-entered local records; production must add authenticated identity and signed approval receipts before multi-user use.

## 6. CACE verification

CACE's connected repository describes a headless CLI:
`python -m cace_studio.cli run EXPERIMENT.cace --seed 0 --output report.json`.
The Merlin adapter invokes that CLI from a configured CACE checkout:

    python3 workers/archive_intake/cace_adapter.py EXPERIMENT_SHA256 ./experiment.cace --cace-root /path/to/Cace-app --database ./data/merlin.sqlite3 --version 3.36.0.dev1

The subject SHA must equal the exact experiment file hash. A receipt is `passed` only when the CACE CLI exits successfully and the report contains explicit PASS statuses; missing or ambiguous verification remains inconclusive. This run receipt does not claim formal proof qualification and records assumptions/axioms as not extracted. Verify a CACE attestation separately:

    python3 workers/archive_intake/cace_adapter.py --cace-root /path/to/Cace-app --verify-attestation ./attestation.json

CACE's own current guidance requires current-source qualification, canonical claim/proof-ledger agreement and qualification-drift checks before formal evidence can be promoted. Merlin does not override those rules.

## 7. Research graph

    python3 workers/archive_intake/research_graph.py merlin-main --database ./data/merlin.sqlite3 --out ./data/research-graph.json

The graph links project artifacts, GitHub commit receipts, CACE verification receipts, engineering metadata and electrical nets. It is a derived read model; the canonical project/artifact and evidence records remain in SQLite.

## 8. CAD/MCFC geometry, simulation and wiring

The `cad_mcfc_model.py` module validates homogeneous 4x4 affine transforms, transforms 3D points, composes frames, validates rigid rotations, checks simulation provenance metadata and normalizes wiring/net relationships. `engineering_registry.py` persists validated metadata and wiring only for registered project artifacts. CAD formats are classified during intake but are never opened or executed by the intake worker.

Example transform input:
    {"kind":"transform","matrix":[[1,0,0,10],[0,1,0,0],[0,0,1,0],[0,0,0,1]],"point":[1,2,3]}

Example wiring input:
    {"kind":"wiring","connections":[{"connection_id":"c1","from_node":"J1","from_pin":"1","to_node":"R1","to_pin":"1","net_name":"VCC"}]}

Simulation metadata requires solver/version, model and input hashes, units, parameters and boundary conditions. Results remain `not_verified` until a separate verifier receipt is attached.

## 9. Tests and trust boundaries

    python3 -m unittest discover -s workers/archive_intake/tests -v

Tests are authored but have not been executed in this environment. No GitHub Actions workflow was added, to conserve the Actions budget.

- Archive contents are never executed, imported, rendered or opened in an application.
- Hashes establish byte identity, not safety, authorship, correctness or provenance.
- Extension classifications are hints, not trust verdicts.
- GitHub commit receipts are point-in-time API records; signed-commit status is separately recorded.
- Hermes transport, Avrea provider dispatch and CACE qualification remain explicit integration boundaries.
- CACE run success is not automatically formal proof qualification.
- CAD transforms are mathematical metadata operations, not a geometry-kernel or solver implementation.
- SQLite is a single-host prototype, not a production multi-user registry.
- No service has been deployed; PR remains draft and requires tests/review.
- Governing invariant: capability grows, authority never expands.
