# Merlin generative media and exact engineering drafting v0.1

## Design principle: one source of truth, two rendering lanes

Merlin now separates engineering truth from visual explanation.

1. **Exact drafting lane:** typed Engineering IR + CAD assembly + coordinate-frame graph + pin/net geometry -> deterministic SVG, connectivity overlays, CSV schedules, JSON manifests and later native CAD/EDA exports.
2. **Generative media lane:** the same source facts -> structured image/video prompts -> optional ComfyUI workflow execution for illustrative renders, exploded-view concepts, assembly walkthroughs and training material.

An image or video model is not permitted to invent or revise dimensions, pin numbers, connectivity, part count, clearances, wire gauge, materials, tolerances or standards. Those values remain in the typed project and are rendered from deterministic geometry. Generative outputs are never imported as authoritative engineering geometry without a separate extraction, dimensional validation and human review process.

## Implemented

- `python/merlin/media_generation.py`
  - Typed `EngineeringMediaBrief` and `EngineeringPromptPack`.
  - Deterministic image prompt, video shot-sequence prompt, negative prompt and coder/developer prompt compiled from the exact project/assembly facts.
  - Prompt provenance includes a machine-readable snapshot of parts, sizes, positions, pins, nets, frames and units.
  - Minimal local ComfyUI API adapter. A user-supplied API-format workflow can include `{{PROMPT}}` and `{{NEGATIVE_PROMPT}}` tokens and be queued at `/prompt`.
  - Defaults to local `http://127.0.0.1:8188`; override with `MERLIN_COMFYUI_URL`. No cloud credentials are required by this adapter.
- `python/merlin/engineering_drafting.py`
  - Deterministic editable SVG top view derived from declared assembly transforms and coordinate frames.
  - Draws component footprint rectangles and a dashed logical straight-line connectivity overlay only where pin coordinates are explicitly supplied.
  - Explicitly labels the result as not routed and not for manufacture.
- `tests/test_media_and_drafting.py`
  - Verifies prompts bind to source facts, reject unsupported durations, preserve ComfyUI workflow templates, and produce deterministic SVG with logical net overlays.
- CI runs the new tests with the existing Merlin engineering suite.

## "Prompt engineering of the coder" contract

The generated coder prompt instructs an implementation agent to:
- treat typed Merlin facts as the only source of truth;
- preserve SI units, part identities and coordinate frames;
- create editable vector/CAD artifacts from explicit coordinates and constraints;
- keep an assumption ledger and report all missing inputs;
- never infer manufacturer ratings, wire gauges, tolerances, material properties or standard clauses;
- add reproducible tests, hashes and a validation report;
- keep image/video models on the presentation side of the pipeline;
- reject contradictory inputs instead of silently filling gaps;
- never declare a design qualified or ready to manufacture.

This makes the model act like a drafting assistant following a controlled engineering brief, rather than a free-form image generator pretending to be CAD.

## Workflow templates

ComfyUI is the preferred first integration because it supports local execution, graph/node workflows, JSON workflow serialization and API integration. Image models and video models can be swapped by selecting different saved workflows without changing Merlin's engineering IR.

Recommended initial workflow classes:
- image: orthographic/isometric presentation render from a deterministic CAD render or reference image;
- image edit: annotate or restyle a render while preserving geometry;
- video: image-to-video using a fixed first frame, slow camera motion, no component transformation;
- video storyboard: deterministic keyframes rendered from CAD first, then optional interpolation/animation.

For exact engineering geometry, use FreeCAD/OpenSCAD/KiCad or a deterministic renderer before any diffusion model. Video generation should animate a validated CAD render, not synthesize the assembly's physical dimensions.

## Research sources and standards spider

Merlin should maintain a public-source research graph. It may ingest public metadata, abstracts, DOIs, official standards catalog entries and user-provided licensed documents. It must respect publisher access controls and must not pretend that an abstract is the full normative text.

Priority IEEE references:
- IEEE Std 315-1975, Graphic Symbols for Electrical and Electronics Diagrams (including reference designation letters). Public DLA ASSIST record shows IEEE315 adoption and reaffirmation metadata: https://quicksearch.dla.mil/qsDocDetails.aspx?ident_number=283880
- IEEE Std 280-2021, Standard Letter Symbols for Quantities Used in Electrical Science and Electrical Engineering. IEEE Xplore metadata describes standardized quantity symbols and units: https://ieeexplore.ieee.org/abstract/document/9540824
- IEEE/ANSI Y32.9-1972, graphic symbols for electrical wiring and layout diagrams used in architecture/building construction. It is a narrower building-construction reference, not a universal modern electronics schematic standard: https://standards.ieee.org/ieee/Y32.9/3037/

The spider should store source title, DOI/URL, publisher, publication date, standard edition/status, access classification, abstract, cited references, extracted claims, relevant Merlin module, evidence hash and review state. Rank sources by direct applicability, authoritative origin, recency/edition, reproducibility and independent corroboration. Do not encode normative clauses from metadata or abstracts alone.

## Ranked next steps

1. **P0 — Native drafting round-trip:** generate a small KiCad project from canonical IR, run ERC/DRC, import the netlist, and compare every pin/net identity against Merlin. Pin exact KiCad version and project rules.
2. **P0 — CAD camera/render pipeline:** export the same assembly to OpenSCAD/FreeCAD, produce top/front/side/isometric SVG or raster references, and bind every image to the exact project hash.
3. **P1 — ComfyUI workflow library:** version image and video API workflows; define model IDs, checkpoints, input/output schemas, resolution, seed, frame count, resource requirements, and license/provenance.
4. **P1 — Video storyboards:** generate deterministic keyframes from CAD, then animate camera paths and overlay declared net paths; reject frame-to-frame geometry drift.
5. **P1 — IEEE/public research spider:** ingest accessible metadata and abstracts, build DOI/reference graph, deduplicate claims, attach standards edition and module mapping, and send high-value unknowns to Merlin's ideonomy queue.
6. **P2 — Visual-to-CAD assist:** extract candidate lines, dimensions and components from hand sketches as hypotheses only; require user confirmation and exact dimensional constraints before updating IR.
7. **P2 — RSI optimization:** measure information gain per CPU-minute and human review minute. Promote a new workflow/model only after held-out geometry fidelity tests, reproducibility, resource bounds, licensing review, and rollback tests.

## Acceptance gates

- Prompt compiler is deterministic for identical source data and brief.
- Prompt provenance hashes match the exact source project and assembly.
- SVG coordinates are traceable to explicit transforms and pin positions.
- No generative image/video output can write into the canonical engineering IR.
- Native EDA round-trip preserves every part reference, pin number and net membership.
- Video keyframes pass geometry-consistency checks against the CAD source.
- Model/workflow license and provenance are recorded.
- CACE receives evidence receipts; no automatic approval or merge occurs.

## Evidence boundary

The new tests validate prompt compilation, template substitution and the deterministic SVG output. They do not prove that a diffusion model will preserve geometry, that the local ComfyUI server is installed, that a specific workflow/model is available, or that a generated illustration is a valid engineering drawing. The adapter has not executed a media-generation job in CI. Native KiCad/FreeCAD round-trip remains the next major engineering task.
