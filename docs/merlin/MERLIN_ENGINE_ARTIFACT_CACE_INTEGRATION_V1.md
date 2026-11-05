# Merlin engine, artifact and CACE integration v1

## Hermes stage composition

`python/merlin/hermes_stage_handlers.py` builds a strict registry for:

- `research`
- `numerical_experiment`
- `proof_search`
- optional `electrical_analysis` when an ngspice executor is supplied

The research, numerical and proof-search executors are explicit required
dependencies. The builder refuses missing executors, missing CACE verifier
callbacks, invalid source repository identities or malformed commit SHAs.
It does not pretend that an absent research provider or proof-search engine is
available.

Every stage executor receives the Hermes task and bounded execution context.
It must return non-empty artifact bytes, a concise summary, a media type and
optional metadata. The handler writes those bytes through
`ResearchEvidenceRecorder`, checks the registry digest, and links the artifact
to the canonical hypothesis graph. It then calls the injected
`CaceVerificationAdapter.verify_artifact` callback with the exact repository,
commit, artifact digest, kind, schema and logical path. Both the result blob
and CACE receipt digest are returned as evidence references. No stage can
promote a hypothesis.

The host process composes the worker only after it has its canonical
stores and real services. The expected wiring shape is:

```python
cace = CaceVerificationAdapter(
    verify_transport=cace_transport.verify_artifact,
    registry=canonical_registry,
    outbox=canonical_outbox,
    graph=canonical_graph,
)
handlers = build_merlin_hermes_handlers(
    evidence_recorder=canonical_evidence_recorder,
    project_id=project_id,
    research_executor=real_research_executor,
    proof_search_executor=real_proof_search_executor,
    artifact_verifier=cace.verify_artifact,
    repository="owner/repo",
    commit_sha=runtime_source_commit,
    requester_id="merlin-hermes",
)
worker = HermesWorker(
    canonical_outbox,
    handlers=handlers,
    approval_validator=approval_service.validate_task,
    lease_validator=mcfc_service.validate_budget,
)
```

The identifiers above describe the injection contract; they are not claims that
those service objects or the CACE transport are already connected in this
repository deployment.

## Numerical and electrical engines

### Linear ODE simulation

`python/merlin/linear_simulation.py` contains a real, deterministic RK4
integrator for the bounded model

`dx/dt = A x + b u`.

The solver validates dimensions, finite values, time interval and maximum
step count. It returns numeric time-series data and a JSON artifact. The
`linear_ode_task_executor` can be supplied as the Hermes
`numerical_experiment_executor`. It is intentionally not described as a
general nonlinear or multiphysics solver.

### ngspice

`python/merlin/ngspice_engine.py` provides a batch adapter for an installed
`ngspice` executable. It validates a restricted netlist subset and rejects
control, shell and external-file directives before execution. Wall time is
bounded; the local binary must exist on PATH. The
`ngspice_task_executor` can be supplied as Hermes `electrical_executor`.

The adapter is not a substitute for a schematic/netlist compiler: callers must
supply a validated SPICE netlist. It does not claim ERC, PCB layout, electrical
safety certification or fabrication sign-off. POSIX process resource limits
and a container supervisor remain deployment responsibilities.

## FreeCAD document import

`python/merlin/freecad_document_bridge.py` generates a macro to open an
operator-selected FCStd document or import STEP/STP, traverse shape objects
and assembly groups, tessellate bounded meshes, and export
`merlin-freecad-document-mesh/1` JSON. The payload contains object identities,
assembly child references, bounds, positions, dimensions, vertices and faces.

The HUD descriptor now preserves imported `objects` and `assemblies`, and
the CAD renderer projects bounded mesh faces as well as the original box
geometry. This is a read-only mesh preview, not a full FreeCAD editing kernel.
The macro has not been run in a FreeCAD installation in this environment.

## Independent CACE receipts

`CaceVerificationAdapter.verify_artifact` verifies that the submitted digest
exists in the canonical registry before sending a request to CACE. It requires
the returned receipt to bind the exact repository, commit, digest, artifact
kind, schema and logical path; it checks independent verifier identity,
source-commit and digest assertions, status and the receipt's own SHA-256.
A The adapter sends the exact registry-verified artifact bytes (base64 and byte
length, capped at 25 MiB) to the independent transport. A `verified` artifact
receipt must additionally affirm both `artifact_schema_validated=true` and
`artifact_content_verified=true`; a digest match alone is not a semantic/domain
validation. It stores the receipt in the
registry and, when a graph is injected, creates a `proof_receipt` node connected
to the subject artifact by a `reviews` edge.

The existing theorem-specific `verify` path remains stricter: verified proof
receipts must confirm kernel checking, exact target declaration, no `sorry`
and a passing axiom audit.

## Current connection state and remaining work

Implemented in source:
- stage-scoped Hermes composition with mandatory CACE artifact-verifier hook
- canonical registry and graph evidence recording
- RK4 linear simulation engine
- restricted ngspice batch adapter
- FreeCAD FCStd/STEP import and bounded mesh export macro
- mesh-aware CAD workspace rendering
- CACE generic artifact receipt validation and optional graph linkage

Not live/verified in this repository session:
- a real research retrieval/execution provider for the `research` stage
- a real proof-search engine for the `proof_search` stage
- installed and executed ngspice binary
- installed and executed FreeCAD process
- a connected CACE transport and independent CACE service response
- runtime construction of Hermes with the actual approval and MCFC validators
- tests or an end-to-end worker run

To activate the complete pipeline, the host runtime must inject its real
research provider, proof-search engine, CACE transport, canonical stores,
approval validator and MCFC lease validator. The numerical and electrical
executors can use the built-in RK4 and ngspice adapters. The FreeCAD macro must
be run by the operator's installed FreeCAD process and its JSON output then
registered as a canonical CAD artifact before CACE attestation.

No merge, deployment, provider activation or external engine installation is
performed by these source changes.

**Capability grows, authority never expands.**
