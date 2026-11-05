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

The outbox supports lease, retry and acknowledgement. Acknowledgements must accept the exact event ID and be returned by the worker that owns the lease. `HermesTransport` is the integration interface for a real Hermes client. Delivery is at-least-once; the receiving Hermes service must deduplicate by event ID. No Hermes endpoint or credentials are configured here, so this PR does not claim live event delivery.

## 5. Avrea approval and dispatch gate

A task must be bound to a canonical approval record, a capability allowlist, resource maxima, timeout and a result manifest. The task's `task_contract_sha256` is computed from canonical JSON with that self-referential field excluded; the approval must bind that exact digest. The approval file must contain `status: approved`. Record an operator approval:

    python3 workers/archive_intake/avrea_dispatch.py record-approval approval.json --database ./data/merlin.sqlite3

Then submit:

    python3 workers/archive_intake/avrea_dispatch.py submit task.json --approval approval.json --policy workers/archive_intake/avrea-policy.example.json --database ./data/merlin.sqlite3

Without a configured Avrea provider, the task remains `approved_waiting_for_provider`; it is not executed. A provider adapter must implement submit/result retrieval and return a result manifest whose artifacts each have a SHA-256 and retrieval URI. The adapter must enforce the supplied CPU, memory, timeout and output limits at the worker/container boundary; the Merlin queue validates and records these limits but cannot enforce a remote worker's OS quotas itself. This repository currently has no Avrea connector or provider credentials, so no Avrea job has been dispatched. Approval records are operator-entered local records; production must add authenticated identity and signed approval receipts before multi-user use.

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

The `cad_mcfc_model.py` module validates homogeneous 4x4 affine transforms, transforms 3D points, composes frames, validates rigid rotations, checks simulation provenance metadata and normalizes wiring/net relationships. Use `engineering_registry.py PROJECT_ID INPUT.json --database ./data/merlin.sqlite3` to persist a `kind: wiring` graph, or add `--artifact-sha256` for `kind: cad` / `kind: simulation` metadata. Wiring pins may fan out on one net but may not be assigned to multiple nets. `engineering_registry.py` persists validated metadata and wiring only for registered project artifacts. CAD formats are classified during intake but are never opened or executed by the intake worker.

Example transform input:
    {"kind":"transform","matrix":[[1,0,0,10],[0,1,0,0],[0,0,1,0],[0,0,0,1]],"point":[1,2,3]}

Example wiring input:
    {"kind":"wiring","connections":[{"connection_id":"c1","from_node":"J1","from_pin":"1","to_node":"R1","to_pin":"1","net_name":"VCC"}]}

Simulation metadata requires solver/version, model and input hashes, units, parameters and boundary conditions. Results remain `not_verified` until a separate verifier receipt is attached.\n\n### Geometry backend and assembly frame graph\n\n`cad_geometry_backend.py` defines a fail-closed geometry-kernel adapter contract for STEP/STP, IGES/IGS and mesh inputs. It verifies the input digest, confines inputs/outputs to configured workspaces, checks explicit backend identity/version and hashes every returned artifact. A backend must be passed explicitly as a Python adapter; there is no automatic executable discovery or shell invocation. Its fixture tests validate contract and receipt integrity only—not CAD topology correctness. Request schema: `schemas/cad-geometry-job-v1.schema.json`. No FreeCAD/OpenCascade kernel is bundled.\n\n`cad_assembly_graph.py` validates a single-root component hierarchy, rejects duplicate IDs, missing parents, cycles and invalid frame matrices, and resolves each component transform into the assembly-root frame using column-vector composition. Its deterministic assembly digest is independent of component input ordering. Schema: `schemas/cad-assembly-graph-v1.schema.json`. This checks frame-graph consistency only; it does not perform collision detection, mating/joint solving, geometric interference checks or topology validation.

## 9. Local smoke test and unit tests

Run the end-to-end smoke fixture without network access or paid services:

    python3 workers/archive_intake/smoke_test_merlin.py

The smoke test creates a temporary ZIP and SQLite database, exercises intake registration, project/artifact queries, Hermes enqueue/retry/lease/acknowledgement, an Avrea approval gate with no provider, CAD frame transforms/inversion, wiring persistence and research-graph edge integrity. Its approval is explicitly a non-production fixture; it does not authorize or execute a real Avrea task. All temporary data is removed when the process exits.

Then run the full unit-test suite:

    python3 -m unittest discover -s workers/archive_intake/tests -v

These commands are local-only. They do not use GitHub Actions, send Hermes events, dispatch Avrea work, or assert CACE formal qualification.

## 10. Tests and trust boundaries

Tests are authored but have not been executed in this environment. No GitHub Actions workflow was added, to conserve the Actions budget.

- Archive contents are never executed, imported, rendered or opened in an application.
- Hashes establish byte identity, not safety, authorship, correctness or provenance.
- Extension classifications are hints, not trust verdicts.
- GitHub commit receipts are point-in-time API records; signed-commit status is separately recorded.
- Hermes transport, Avrea provider dispatch and CACE qualification remain explicit integration boundaries.
- CACE run success is not automatically formal proof qualification.
- CAD transforms and assembly graphs are mathematical metadata operations. The geometry backend is an adapter contract and artifact-integrity boundary, not a bundled FreeCAD/OpenCascade kernel or simulation solver.
- SQLite is a single-host prototype, not a production multi-user registry.
- No service has been deployed; PR remains draft and requires tests/review.
- Governing invariant: capability grows, authority never expands.
\n\n### Optional FreeCAD adapter\n\nSee [`FREECAD_ADAPTER.md`](FREECAD_ADAPTER.md). `freecad_adapter.py` is an explicit, opt-in adapter that requires a caller-supplied FreeCAD Python runtime. It can import supported CAD files, report shape validity/topology counts/bounds/placements, and export STL meshes with explicit tessellation settings. No FreeCAD runtime is bundled or launched by Merlin; no actual FreeCAD run is claimed. Source assembly hierarchy reconstruction, unit/frame conversion, collision and joint analysis, and solver execution remain future work.\n

### FreeCAD runtime image and assembly export

The optional adapter now includes `build_assembly_graph(...)`, which exports FreeCAD document Group relationships into Merlin's canonical assembly frame graph. The caller must supply a verified artifact-digest resolver and an explicit parent-relative transform resolver; the adapter deliberately does not guess whether a FreeCAD placement is global or parent-relative. The exported graph is passed through `resolve_assembly` before return.

A pinned headless runtime image and module probe are in `freecad-runtime/`. Build from the repository root with:

    docker build -f workers/archive_intake/freecad-runtime/Dockerfile -t merlin-freecad:debian-bookworm .

Then probe with networking disabled:

    docker run --rm --network none merlin-freecad:debian-bookworm

This image has not been built or deployed to Avrea. No Avrea runner connector is available in this session; see `freecad-runtime/README.md` for the operator handoff and isolation requirements.

## FreeCAD geometry worker execution

The pinned FreeCAD runtime now includes `freecad-runtime/run_geometry_job.py`. It accepts a JSON contract and CAD input from a dedicated input workspace, invokes the explicit FreeCAD adapter, validates output artifact paths and SHA-256 digests through the geometry backend contract, and atomically writes `geometry-receipt.json`. The request file must itself be inside the mounted input workspace; input and output workspaces must be separate and non-nested.

See [freecad-runtime/README.md](freecad-runtime/README.md) for the build, module probe and isolated container invocation. Host/Avrea policy must enforce resource ceilings and network/filesystem isolation. The job runner is implemented and has mocked regression tests, but neither the tests nor the FreeCAD image have been executed in this session. No live Avrea dispatch or real CAD processing is claimed.
