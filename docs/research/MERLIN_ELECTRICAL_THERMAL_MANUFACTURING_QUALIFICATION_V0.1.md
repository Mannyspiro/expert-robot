# Merlin electrical, thermal and manufacturing qualification research v0.1

## Objective and boundary

Move from a geometric wire-route proposal to a traceable, multi-domain engineering review. The software may calculate explicit quantities, compare supplied limits, generate logical connection artifacts, and expose missing proof obligations. It must never infer missing ratings or convert a green software test into a claim that hardware is safe, compliant, or ready to manufacture.

The three outputs remain distinct:
- **Geometry candidate:** a path exists in the current simplified CAD model.
- **Engineering screening:** supplied data and declared models pass selected calculations.
- **Qualified release:** applicable standards, authoritative manufacturer data, representative tests, manufacturing controls, and independent sign-off are complete.

Merlin v0.1 implements the first two only, and the second only when users supply adequate source data. Release authority remains outside the model.

## Ranked implementation and research priorities

### Rank 1 — Typed single source of truth and provenance
Use one revisioned engineering project for parts, pins, nets, frames, component geometry, conductor specifications, constraints, and evidence. Every derived schematic, netlist, route, thermal result and report must bind to the same project/assembly revision hashes. Missing data is represented as unknown, not silently defaulted.

**Exact foundation:** typed graph/hypergraph, SI dimensional analysis, rigid transforms, deterministic serialization, content-addressed receipts.

### Rank 2 — Electrical design-rule and protection review
Inputs required per circuit: operating and transient voltage envelope, load and fault current, duty cycle, conductor material/area/stranding, manufacturer resistance and ampacity data, insulation system and rating, connector/contact ratings, protective device characteristics, grounding/bonding topology, installation method, grouping, ambient conditions, and jurisdiction/product class.

Computations and proof obligations:
- conductor ampacity after manufacturer- and installation-specific derating;
- DC/AC voltage drop with correct complete circuit path, temperature and contact assumptions;
- pin, connector and component voltage/current limits;
- overcurrent and short-circuit coordination, including protective-device clearing and conductor withstand;
- insulation coordination, creepage, clearance, pollution degree, material group, altitude and transient category;
- protective bonding continuity and fault-current path;
- EMC, shielding, return path and signal-integrity constraints where applicable.

**Do not derive ampacity from gauge alone. Do not derive creepage/clearance from voltage alone.** The current implementation compares user-supplied reviewed limits; it does not calculate standard tables or prove protection coordination.

### Rank 3 — Thermal model with correlation
Start with transparent lumped models for screening: (P=I^2R), temperature-corrected conductor resistance, thermal resistance/capacitance networks, and worst-case ambient/load envelopes. Move to coupled finite-element/CFD or detailed cable-bundle models when geometry, enclosure airflow, adjacent heat sources, transients, or high power make lumped assumptions inadequate.

Required proof:
- material properties and temperature coefficients from traceable sources;
- thermal boundary conditions and cable grouping/install method;
- convergence and energy-balance checks;
- sensitivity and uncertainty analysis;
- correlation against representative physical temperature measurements over worst-case load/ambient conditions.

A converged model is not validated merely because it converges. The current v0.1 model is a single lumped steady-state estimate and is explicitly evidence-dependent.

### Rank 4 — Mechanical harness and manufacturing model
Replace centerline polylines with swept cable solids and bundle envelopes. Model manufacturer minimum bend radius, connector exit direction, strain relief, service loops, clips, abrasion, separation, moving joints, installation sequence, tolerance stack-up, enclosure access and maintainability. Run exact or appropriately conservative solid collision checks. AABB checks remain broad-phase only.

Manufacturing outputs should include controlled drawings, wire/cable schedule, cut lengths and tolerances, connector/pin tables, BOM, labels, assembly sequence, inspection plan, continuity/pinout test plan, and revision-linked acceptance records. The current exports are logical drafts only.

### Rank 5 — Schematic / EDA / CAD integration
Use the typed engineering IR as the interchange layer:
1. Generate a logical connectivity graph and review-only wire schedule.
2. Add native EDA generation only through a version-pinned supported interface (for example, a KiCad project generator), then run ERC and DRC using the exact tool version and saved rule set.
3. Import EDA netlists and compare pin/net identity with Merlin's canonical project; reject discrepancies.
4. Export mechanical assemblies through a supported CAD kernel/format; preserve frame transforms and units.
5. Generate swept harness geometry and compare it to enclosure/board/component solids.
6. Round-trip generated artifacts into Merlin and hash them before qualification.

Never label a Graphviz connectivity diagram as a circuit schematic. Never label OpenSCAD box geometry as a manufacturing CAD model.

### Rank 6 — Independent verification and qualification evidence
Every result must carry: input revision/hash, tool/version, parameter set, assumptions, units, solver/check status, warnings, evidence artifact hashes, reviewer identity/role, and expiration/review state. Re-run checks after any source, geometry, tool, or standards revision. Separate the authoring worker from the verifier and approval authority.

## Current Merlin implementation in this increment

- `python/merlin/wire_qualification.py`: explicit ampacity comparison using manufacturer ampacity and supplied derating; DC resistive voltage-drop estimate using a supplied complete circuit-loop length; insulation rating comparison; comparison against a separately reviewed clearance requirement; lumped temperature estimate with resistance temperature correction; swept bend-radius and harness slack checks; required-evidence blockers.
- `python/merlin/wiring_exports.py`: logical Graphviz connectivity graph, review-only CSV wire schedule, and JSON schematic manifest. All outputs are explicitly marked non-release; wire specification is never invented.
- `tests/test_wire_qualification.py` and `tests/test_wiring_exports.py`: deterministic tests for calculations, limit failures, missing correlation, missing bend geometry, unknown evidence and export labels.
- Avrea CI includes these test modules. A passing CI run proves only that the implemented software tests pass for that commit; it does not qualify an actual device.

## Evidence required before a real design can be called qualified

The report currently blocks until evidence is supplied and independently reviewed for:
1. Component and connector datasheets.
2. Wire and insulation datasheet.
3. Applicable standard and product-class determination.
4. Schematic electrical-rules check.
5. PCB design-rules check or justified not-applicable record.
6. Insulation coordination and clearance review.
7. Overcurrent and short-circuit coordination.
8. Protective bonding and grounding review.
9. Thermal model correlation or physical test.
10. Mechanical tolerance and collision review.
11. Harness workmanship and process plan.
12. Continuity and pinout test.
13. Insulation resistance and dielectric test.
14. Independent engineering sign-off.

Evidence is accepted only as a reviewed artifact reference with a SHA-256 and reviewer field. The v0.1 schema is a gate tracker, not a cryptographic identity provider or credential system; stronger signed attestations are a later task.

## Standards and applicability research references

These are standards families to map to product type and jurisdiction; Merlin must not assume every one applies to every project. Access to full normative text and qualified interpretation is required before encoding clause-level checks.

- IEC 60204-1:2016+A1:2021, electrical equipment of machinery. IEC's publication page identifies the consolidated edition and its scope for machinery electrical equipment: https://webstore.iec.ch/en/publication/71256
- IEC 60664-1:2020+A1:2025, insulation coordination for low-voltage supply systems; includes clearance, creepage and solid insulation considerations: https://webstore.iec.ch/en/publication/59671
- IPC/WHMA-A-620F (October 2025), requirements and acceptance for cable and wire harness assemblies; its scope is workmanship/manufacture and acceptance, not circuit design: https://www.electronics.org/TOC/IPC-WHMA-A-620F-TOC.pdf

## Next research experiments, ordered by information gain per cost

1. Create a source-data schema and evidence loader for manufacturer conductor, connector and insulation properties.
2. Add circuit-level current path semantics (outbound and return conductor, branches, parallel conductors, protective conductor) before expanding voltage-drop calculations.
3. Add a verified standards applicability record keyed by jurisdiction, product class, environment, edition and amendment.
4. Add a transient thermal RC network with energy-balance tests and uncertainty propagation.
5. Integrate native EDA generation and ERC/DRC with pinned versions and round-trip netlist comparison.
6. Add swept cable geometry, bend radius and exact solid collision using a supported CAD kernel.
7. Add test-fixture templates and immutable lab evidence ingestion.
8. Only after these pass should Merlin optimize routes against weighted objectives (length, bend count, thermal separation, EMI class, serviceability, cost and tolerance), subject to hard constraints. A weighted score must never trade away a mandatory safety constraint.

## CACE and MCFC boundaries

CACE owns evidence validation, reproducibility, independent verification, approval-gated state transitions, rollback and audit receipts. It cannot infer domain approval from a score or model confidence.

MCFC remains the virtual compute fabric: typed CPU/memory/GPU resources, resource budgets, scheduling, leases, telemetry, and bounded workers. It executes simulation/EDA/CAD jobs under resource limits; it does not define physical coordinate frames. XMG / coordinate-frame contracts describe the same physical design across assembly, board, component, pin, harness and sensor frames.

Capability grows, authority never expands.

## Formal proof layer (conditional mathematics)

`formal/MathAI/WireQualification.lean` adds conditional Lean theorems for:
- derated ampacity implying the nominal manufacturer ampacity bound;
- nonnegativity of the declared DC resistive voltage-drop expression;
- positivity of temperature-corrected resistance under stated assumptions;
- uniqueness of a fixed point for the affine lumped thermal model when feedback gain is below one;
- scalar clearance and swept bend-radius comparisons.

The file is imported into `formal/MathAI.lean`, and each theorem is included in
`formal/MathAI/Audit.lean` for kernel-visible axiom reporting. The theorem
registry now marks all six as **verified** after Dedicated Lean Formal Qualification run #471 passed. This status certifies the Lean propositions and audited build only, not physical inputs or a real product.

These proofs validate algebraic implications inside declared models. They do
not validate the source datasheets, the selected standard, the CAD measurement,
the thermal boundary conditions, or the real physical assembly. In particular,
the thermal fixed-point uniqueness theorem is not a proof that the physical
system is represented by the lumped model.
