# Merlin P0 Repository Reconciliation and Proof Strategy Observatory v0.1

**Snapshot:** 2026-11-04  
**Repository:** `Mannyspiro/expert-robot`  
**Working branch:** `feat/merlin-lean-proof-optimization-atlas-20261104`  
**Policy:** capability grows, authority never expands.

## 1. Reconciliation result

The active draft chain is:

`#67 network/Hermes/Kokoro/Engineering IR` → `#70 Academic Spider, hypothesis ledger, CAD/frames/connectivity, proof receipts` → `#72 Equation Atlas/XMG/simulation/MCFC/wiring/Lean` → `#75 proof optimization atlas and chat idea ledger`.

All four PRs were observed as **open, draft and unmerged** at this snapshot. Their base/head chain is explicit:

| PR | Base | Head | Reconciliation |
|---|---|---|---|
| #67 | `main` | `feat/merlin-hermes-kokoro-qualified-20261102` | foundational runtime and typed engineering contracts |
| #70 | #67 head | `feat/merlin-academic-spider-v01-20261103` | research graph, CAD frames, physical connectivity, receipt intake |
| #72 | #70 head | `feat/merlin-real-world-equation-atlas-v01-20261104` | equation atlas, XMG, simulation, MCFC, CAD/wiring and formal increment |
| #75 | #72 head | `feat/merlin-lean-proof-optimization-atlas-20261104` | proof strategy specification and durable idea ledger |

No PR merge is assumed. PR #75 head at reconciliation was `d0a057100d2f64d278e71fad3881f801ebb4963e`; PR #72 head was `ddab7c3fe732bcde7c94e2c645487055cfd311f0`. Both current combined-status lookups returned no status entries. PR #75's description reports failed Actions runs and a failed preview build; this branch is **not qualified**. A missing current status entry is not a pass.

## 2. Module-to-test-to-evidence map

The paths below were found in PR #70/#72 changed-file inventories or fetched from the PR #72 branch. The new Observatory files and test were added to PR #75. A test file's existence is not proof it passed on the current head. “Latest prior qualification” means the latest run specifically named in the PR's recorded verification history, not a fresh rerun at PR #75 head.

| Module / capability | Implementation files | Focused tests | Latest prior qualification / receipt | Unresolved dependencies and limits |
|---|---|---|---|---|
| Representation / object-view graph | `merlin/representation_graph.py` | `tests/test_merlin_representation_graph.py` | Catalog run #66 passed on PR #72 head; exact representation graph test step passed in current metadata | Exact rational square-matrix frame graph only; needs typed bridge to CAD frame IDs, units, domains/codomains, lossiness and engineering revision hashes |
| Rotation representations | `merlin/rotation_representations.py` | `tests/test_merlin_rotation_representations.py` | Catalog run #66 passed quaternion/Cl(3,0) step | Need consistent conventions and conversion invariants across complex, matrix, quaternion and geometric-algebra representations |
| Spherical holonomy | `merlin/spherical_holonomy.py` | `tests/test_merlin_spherical_holonomy.py` | Catalog run #66 passed spherical curvature/holonomy step | Scope is current implemented model; broader manifolds/curvature claims need independent derivations |
| Engineering IR | `python/merlin/engineering_ir.py` | `tests/test_engineering_ir.py` | Avrea CI #1418 passed for head `5d5635de04560f260f57da0ffda797e510e45ab9`; later PR #72 CI #1428 passed at `391fd21f8954614c642c918ff5224b5ae65c0cc1` | IR currently has typed parts/pins/nets and mm geometry; no certification, native EDA round-trip or fabrication sign-off |
| Coordinate frames / CAD assembly | `python/merlin/coordinate_frames.py`, `python/merlin/cad_assembly.py` | `tests/test_coordinate_frames.py`, `tests/test_cad_assembly.py` | Included in Avrea CI #1418; later broad CI #1428 | Rigid transforms and conservative AABB only; multi-instance identity, joints/DOF, B-rep collision and tolerance stack-up remain incomplete |
| Physical connectivity | `python/merlin/physical_connectivity.py` | `tests/test_physical_connectivity.py` | Included in Avrea CI #1418 / #1428 lineage | Pin positions/directions are supplied inputs; no inferred datasheet truth, full harness geometry or electrical certification |
| Lean/Avrea proof receipt intake | `python/merlin/lean_proof_receipt.py` | `tests/test_lean_proof_receipt.py` | Receipt-ingestion tests included in PR #70 CI #1240; THTG receipts are stored at `research/merlin/proof_receipts/avrea_thtg_2026-11-04.json` | Validator checks receipt structure but does not independently authenticate remote Actions logs or compile Lean |
| Theorem registry / formal audit | `formal/theorem_registry.json`, `formal/MathAI/Audit.lean`, `formal/MathAI/EquationAtlas.lean`, `formal/MathAI/WireQualification.lean`, `formal/MathAI/XMGComposition.lean` | Formal workflow `.github/workflows/formal-qualification.yml`; registry/audit checked by dedicated formal job | Latest named formal qualification: run #472, head `6921c984b77852d90b4bc2a3232685f39d4d66e8`; theorem registry, pinned package build, audited-root replay, axiom report and manifest immutability were reported passed | This is not qualification of later PR #72 head `ddab7c3...` or PR #75 head. Exact theorem statement and assumptions remain the promotion unit |
| THTG conditional proofs | receipt JSON above | formal workflow and receipt-ingestion tests | Receipt records three theorem-specific successful runs: #41761258888, #41762355488, #41763911516. Later #472 formal registry qualification supersedes earlier formal qualification for its covered registry snapshot | The printed-beta theorem concerns exact printed rational coefficients, not correctness of the physical FRG flow; Page-curve theorem is a counterexample to a proposed maximum, not validation of the model |
| Equation Atlas schema / normalization / symbolic checks | `python/merlin/equation_atlas/{models,normalize,dimensions,operators,symbolic_checks,receipts}.py` | `tests/test_merlin_equation_atlas.py`, `tests/test_merlin_equation_atlas_schema.py`, `tests/test_merlin_evidence_receipts.py` | Broad CI #1428 named as passed for its then-tested head | 80 atlas entries are explicitly UNVERIFIED; synthetic checks are not empirical validation or formal proof |
| Simulation engine / composed models | `python/merlin/equation_atlas/simulation.py`, `python/merlin/equation_atlas/experiments/*.py` | `tests/test_merlin_simulation_engine.py`, `tests/test_merlin_composed_models.py`, plus signal/stochastic/biological tests | Avrea CI #1366 passed at `a1c551bde110cc72a93bf7a255adf3161930a57a`; later broad CI #1428 is recorded in PR #72 | Explicit Euler stability limits; synthetic seeded data; no empirical model adequacy or GPU runtime qualification |
| XMG glyph registry / normalizer / confluence | `merlin/glyph_foundry.py`, `merlin/glyph_normalizer.py`, `merlin/glyph_confluence.py`, `formal/MathAI/XMGComposition.lean` | `tests/test_glyph_foundry.py`, `tests/test_glyph_normalizer.py`, `tests/test_glyph_confluence.py`, `tests/test_merlin_xmg_operator_contract.py` | PR #72 records a later correction to natural-valued termination relation; current head's formal rerun pending | Lean abstract termination theorem does not automatically prove the Python rewrite engine's concrete measure decreases; critical-pair coverage and semantic preservation remain separate |
| Wiring route / qualification / exports | `python/merlin/wire_routing.py`, `python/merlin/wire_qualification.py`, `python/merlin/wiring_exports.py` | `tests/test_wire_routing.py`, `tests/test_wire_qualification.py`, `tests/test_wiring_exports.py` | Avrea CI #1418 / #1428 lineage; six conditional wire theorems reported verified in registry by formal run #472 | Not ERC/DRC, standards certification, protection coordination, validated thermal correlation or manufacturing release |
| MCFC compute fabric | `python/merlin/cpu_fabric/leases.py`, `python/merlin/cpu_fabric/workload_scheduler.py` | `tests/test_workload_leases.py`, `tests/test_workload_scheduler.py` | PR #72 workflow `.github/workflows/merlin-cpu-compute-fabric.yml`; no separately named latest qualification receipt in PR body | Virtual resource model only; live heterogeneous GPU/CPU capacity, durable distributed workers and production scheduling remain unqualified |
| Academic Spider / source graph | `python/merlin/academic_spider.py`, `python/merlin/academic_source_store.py`, `python/merlin/openalex_public.py`, `python/merlin/academic_graph.py` | matching `tests/test_academic_*.py`, `tests/test_openalex_public.py` | PR #70 CI #1240 reported passed for research tests | No live crawl reported; source metadata is discovery evidence, not scientific truth; licensing/robots/rate limits remain mandatory |
| Hypothesis ledger / research council | `python/merlin/hypothesis_ledger.py`, `python/merlin/research_council.py` | `tests/test_hypothesis_ledger.py`, `tests/test_research_council.py` | PR #70 CI #1240 reported passed | Status transition records do not themselves run experiments or independently verify claims |
| Project registry / persistence / archive intake | `python/merlin/project_registry.py`, `python/merlin/foundation_store.py`, `python/merlin/archive_intake.py` | `tests/test_project_registry.py`, `tests/test_foundation_store.py`, `tests/test_archive_intake.py` | PR #72 CI lineage; no latest per-module receipt isolated | Need full archive intake reconciliation and registry-to-Hermes/CACE wiring evidence |
| Resource probe / media / drafting | `python/merlin/resource_probe.py`, `python/merlin/media_generation.py`, `python/merlin/engineering_drafting.py` | `tests/test_resource_probe.py`, `tests/test_media_and_drafting.py` | Media/drafting tests included in Avrea CI #1428; no real ComfyUI generation in CI | Prompt compiler and editable SVG are drafts; native CAD/EDA round-trip and real media backend remain unqualified |

### Exact current status

- PR #72 records Avrea CI #1428 passed at `391fd21f8954614c642c918ff5224b5ae65c0cc1`, and Lean Formal Qualification #472 passed at `6921c984b77852d90b4bc2a3232685f39d4d66e8`.
- PR #72 later advanced to `ddab7c3fe732bcde7c94e2c645487055cfd311f0`. A targeted Mathematical Idea Catalog run #66 (run ID `41890294029`) passed on this exact head: stable-ID/relation validation, catalog tests, exact multi-representation algebra tests, quaternion/Cl(3,0) correspondence, spherical holonomy tests and compilation of the three representation modules. This is a focused math-catalog pass, not the full Merlin build or formal qualification; the Lean compilation, Avrea benchmark rerun and full build remain pending.
- PR #75 advances to `d0a057100d2f64d278e71fad3881f801ebb4963e`; its description reports failed Actions runs and no Avrea qualification for its ledger increment. Current combined-status lookup returned no entries and the PR-triggered workflow-run lookup returned no runs for this SHA. Therefore **there is no qualified run for the current PR #75 head**.

## 3. Proof Strategy Observatory implementation

Added on the PR #75 branch:

- `python/merlin/proof_observatory.py`
- `tests/test_proof_observatory.py`

The subsystem records every attempt, including failures, with:
- theorem ID, normalized statement hash and assumptions hash;
- mathematical domain and object-view representation IDs;
- tactic sequence, failure stage, elapsed time, heartbeats and peak memory;
- source commit/hash, Lean version, Mathlib revision and import-closure hash;
- kernel-check, sorry, exact-target and workflow-run fields;
- axiom dependency list.

SQLite observations are append-only through the public API and use a SHA-256 predecessor chain. Chain verification detects altered payloads or reordered/missing links. Cross-domain links explicitly bind a theorem to one or more object-view IDs and an Engineering IR project revision hash plus a proof-receipt hash.

Adaptive ranking is deliberately strict: it only includes kernel-checked, exact-target, no-sorry successful attempts with a workflow URL; it requires at least three observations for the same tactic sequence, exact statement hash, assumptions hash, domain, Lean version and Mathlib revision. It ranks reliability first, then median heartbeats and elapsed time. It does not infer strategy quality from a single success.

### Integration contract

- **Object-view graph:** use the stable object-view ID and representation/frame ID as explicit references. The proof attempt stores representation IDs; the cross-domain link stores the object-view ID.
- **Engineering IR:** bind to the project identity and the exact canonical revision SHA-256. A proof about a transform, coordinate map, dimension constraint or netlist invariant must name the exact project revision it constrains.
- **CACE/Avrea:** a trusted qualification workflow supplies the run URL, exact source commit/hash, pinned toolchain, kernel-check result and axiom audit. The Observatory stores and indexes that evidence; it does not authenticate GitHub or invoke Lean itself.
- **Hypothesis ledger:** receipt linkage remains separate from status promotion. A verified theorem may support a hypothesis only when theorem assumptions match the hypothesis claim.

The bridge is intentionally reference-based: it does not silently infer that a mathematical theorem validates an engineering object.

## 4. P0 unresolved dependencies

1. Run the new Observatory test suite and the full Merlin focused suite on the exact PR #75 head.
2. Fix and rerun PR #75's failing Actions workflow; inspect job logs rather than infer the failure from a summary.
3. Add a canonical serializer/hash function for EngineeringProject revisions and make it the only source of the Engineering IR revision hash supplied to cross-domain links.
4. Add object-view node export with stable IDs, source/target frame IDs, dimensions, units, map direction, invertibility and invariant-preservation metadata; connect those IDs to CAD CoordinateFrame IDs without conflating representation changes with physical motion.
5. Add a receipt importer that maps trusted formal-qualification artifacts to ProofAttempt records while preserving exact theorem declaration, assumptions, source SHA, Lean/Mathlib revisions and axiom report.
6. Add a dependency extractor from Lean declarations into a theorem DAG; the existing theorem registry's `uses` field is a starting point, not yet a complete imported-lemma dependency graph.
7. Keep proof optimization disabled until paired baseline/candidate measurements exist for at least three repetitions on identical theorem statements and assumptions.
8. Re-run Avrea/Lean on the final PR #75 commit; do not inherit qualification from an ancestor commit.

## 5. Acceptance gates

- Every module row has an implementation path, focused test path, latest exact qualified run or explicit “none”, and named unresolved dependencies.
- Every proof attempt is preserved, successful or not.
- No strategy ranking crosses theorem statement, assumption, Lean version or Mathlib revision boundaries.
- Every object-view/Engineering IR bridge carries explicit IDs and content hashes.
- No evidence receipt is interpreted as proof of empirical adequacy or engineering safety.
- No merge, deployment or promotion occurs automatically.
