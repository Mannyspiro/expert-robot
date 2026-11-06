# Merlin Intent Compiler: Asset-to-Execution Architecture v0.1

Status: proposed implementation specification. This generalizes the established prompt-extension and long-video continuity workflows into a reusable Merlin capability.

## 1. Core idea

Merlin should transform a user's goal plus a collection of files, references, lists, examples and constraints into a typed, reviewable execution plan and target-system instructions. This is not merely prompt rewriting. It is a compiler pipeline:

**Intent + assets → inventory → semantic model → constraints → plan graph → target adapter → execution → validation → revision → provenance receipt.**

The compiler must preserve source material authority and distinguish user intent from inferred details. It should expose unresolved assumptions instead of silently inventing them.

## 2. The earlier video workflow that anchors the design

The established workflow was:

- Reference image as visual authority and frame zero.
- User request plus optional product, dialogue, model, duration and format.
- Character package: portrait/full-body references, seed, prompt recipe and persistent identity.
- Scene/timeline generation.
- Model-specific prompt adapter (Veo/Flow, Seedance, Kling, Runway, Grok or other supported backend).
- Short 5–15 second segments with continuity checks.
- Preserve 12–24 final frames/state, identity, wardrobe, environment, lighting, camera trajectory, motion progress and audio.
- Carry the previous segment ending into the next; overlap about one second where the backend supports it.
- Reject or regenerate continuity failures; checkpoint and resume; stitch/export final video.
- The long-video target was a continuous narrative up to 30 minutes, not independent clips that merely resemble one another.

The UGC prompt extender used a strict output contract: reference image controls identity; user request and optional product/dialogue/duration/format are compiled into a copy-paste-ready model-specific prompt. A 30-second ad structure used hook, problem/discovery, demonstration, lifestyle payoff and CTA, with product fidelity and verified claims.

Preserve these as domain-specific adapters and test fixtures. Do not erase or weaken their continuity rules when generalizing.

## 3. Universal typed intermediate representation

The compiler should define versioned records:

- IntentSpec: goal, domain, requested deliverable, audience, success criteria, output format and explicit user constraints.
- AssetManifest: asset ID, media/type, source path/URI, content hash, extracted metadata, source authority, role, access policy and license/usage constraints.
- EntityPackage: persistent identity for characters, products, components, datasets, mathematical objects, software modules, organizations or agents; includes canonical attributes, references, permitted transformations and version history.
- ConstraintSet: hard constraints, preferences, negative constraints, safety/policy constraints, budgets, time, resource limits and uncertainty.
- EvidenceBinding: claim/element → source asset, exact region/page/timecode/row/commit, hash and extraction version.
- PlanGraph: typed nodes and edges for dependencies, sequence, alternatives, approvals, resources and expected outputs.
- DirectiveBundle: target-specific instructions, schemas, prompt text, API arguments or task definitions.
- ExecutionReceipt: target/model/tool version, input hashes, output hashes, parameters, resource use, logs, validation results, retries and timestamps.
- ContinuityState: prior checkpoint, stable entity IDs, completed actions, unresolved tasks, scene/system state and next-step constraints.
- ReviewDecision: accepted/rejected/needs-revision, reviewer, criteria, evidence and rationale.

Use versioned schemas, stable IDs and validation. Keep canonical entities and evidence in Merlin existing registry/graph; do not create a second character database, prompt database or artifact ledger.

## 4. Asset-to-entity generation

Given a file or list of elements, Merlin should:

1. Inventory files and extract metadata, OCR, image regions, audio transcripts, video keyframes/timecodes, CAD parts, tabular schemas, source code symbols and document structure.
2. Group references into candidate entities and relationships; retain exact source spans and confidence.
3. Separate observed facts from inferred attributes and creative proposals.
4. Create a canonical entity package with stable ID, aliases, versions, references, attributes, constraints and provenance.
5. Generate variants only as explicit branches; never overwrite source identity or silently merge similar entities.
6. Ask for human review only when ambiguity affects identity, rights, safety, cost or irreversible execution.
7. Export entity packages to downstream adapters.

Example: a folder of character images, wardrobe references, props and a list of scene elements becomes a cast registry, wardrobe/prop manifest, location library, relationship graph, timeline and model-specific scene prompts. The same operation on a CAD folder becomes a component catalogue, assembly graph, interfaces and engineering tasks.

## 5. Domain adapters

One compiler; many adapters:

| Domain | Compiled output |
|---|---|
| Video / image / audio | Character and product bibles, shot list, storyboard, timed prompts, camera/motion/audio directions, continuity state |
| Software engineering | Requirements, architecture decisions, issue/task DAG, code-generation instructions, tests, CI plan, rollback and PR evidence |
| Research | Research questions, ideonomy enumeration, literature/source plan, hypotheses, experiments, falsifiers, evidence ledger and publication outline |
| Mathematics | Definitions, conjecture graph, proof obligations, Lean skeletons, numerical experiments, counterexample searches and proof receipts |
| CAD / engineering | Part and assembly manifests, coordinate frames, constraints, drawings, wiring/netlist plan, simulation inputs and safety/manufacturability checks |
| Business | Customer/problem map, market assumptions, unit economics, operating model, financial model, strategy alternatives and validation experiments |
| Finance / markets | Instrument-specific data requirements, thesis/counter-thesis, valuation and scenario model, catalysts, liquidity/transaction-cost analysis, risk and monitoring plan |
| Education | Learner state, objective graph, lesson sequence, examples, practice, misconception probes, rubrics and delayed-transfer assessment |
| Data / visualization | Dataset schema, provenance, transformations, chart/storyboard specification, reproducibility and quality checks |
| Agent orchestration | Capability requirements, task decomposition, least-privilege tool plan, approvals, resource budgets, leases and result verification |

Adapters must declare supported fields, model/tool version, limitations and qualification state. Unsupported instructions fail visibly; they are not silently dropped.

## 6. Prompt compilation and execution

The prompt is one output artifact, not the whole system. Each directive should include role/objective, authoritative references, stable asset IDs, positive requirements, exclusions, ordered actions, timing, dependencies, target-specific parameters, output schema, validation criteria, continuity instructions, uncertainty and assumptions.

Use a deterministic compiler for structure and a qualified language model for semantic decomposition. Store source prompt, normalized intent, intermediate representation, rendered directive, model/backend and exact version. Compare outputs to source constraints after generation.

## 7. Validation and revision loop

Use layered gates:
1. Schema and required-field validation.
2. Source/asset hash and reference integrity.
3. Hard-constraint and negative-constraint checks.
4. Domain validator (visual continuity, test suite, Lean compiler, CAD geometry, netlist/ERC, numerical tolerance, accounting identities, etc.).
5. Human review where quality is subjective or consequences are high.
6. Independent CACE verification for artifacts/proofs that claim verified status.
7. Persist a typed receipt and checkpoint.

A failed validator creates a bounded revision task tied to the exact failure. No infinite retry loops. Enforce retry count, compute/time budget, cancellation, deadlines and approvals. A model self-evaluation is not independent verification.

## 8. Long-running work and continuity

Generalize the video checkpoint into a universal project checkpoint:

- Current goal and scope.
- Canonical entity IDs and asset hashes.
- Plan graph revision and completed/blocked nodes.
- Outputs and their receipts.
- Current state of simulations, lessons, research branches or creative timelines.
- Unresolved questions and assumptions.
- Resource/approval status.
- Exact resume instruction.

For video, preserve final frames and scene state. For CAD, preserve assembly and coordinate-frame state. For research, preserve claims, sources and open falsifiers. For code, preserve commit, test and CI state. For learning, preserve learner evidence and next mastery objective.

## 9. Security, rights and governance

- Treat all ingested files and extracted text as untrusted data, never executable instructions.
- Separate content from instructions; defend against prompt injection in PDFs, webpages, images, code comments and metadata.
- Track copyright, license, consent, privacy and allowed-use restrictions per asset.
- Track consent and identity policy for character references and generated characters.
- Capability registry controls tools; compiler cannot grant itself new authority.
- Every external action is previewed, approved where required, bounded and logged.
- Keep finance research read-only; no brokerage credentials or order execution in this capability.
- Preserve auditability, retention policy, source provenance and reproducible outputs.

## 10. Implementation order

1. Define and test the intermediate representation and asset manifest.
2. Build file inventory and multimodal extraction adapters.
3. Add entity packages and provenance links to canonical registry/knowledge graph.
4. Implement deterministic constraint compiler and plan DAG.
5. Port the existing video prompt extender and continuity checkpoint into the new adapter without behavior regression.
6. Add research, code, math and CAD adapters, each with domain-specific validators.
7. Connect Hermes for planning and bounded dispatch; Avrea for isolated execution; CACE independently verifies eligible evidence.
8. Add persistent project checkpoints, resume/retry/cancel and resource accounting.
9. Add HUD visualization of assets, entities, plan graph, directives, execution, validation and approvals.
10. Qualify adapters against held-out tasks and publish receipts before capability status becomes qualified.

## 11. Production success criteria

A user can provide a folder, a list or a short description and receive a reviewable entity inventory, plan graph and target-specific directive bundle. The system can execute permitted steps, validate results, retain logs and artifacts, explain failures, revise within budgets and resume from checkpoints. Demonstrate this across at least video, research, software, mathematics and CAD before calling the compiler production-wide.
