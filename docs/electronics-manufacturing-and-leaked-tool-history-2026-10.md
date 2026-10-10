# Electronics, manufacturing, and government/leaked security tooling — research atlas

Date: 2026-10-10. Audience: Expert Robot research / CACE math-qualification pipeline.
This is **reference research and non-operational historical analysis**, not hardware
manufacturing validation, exploitation guidance, endorsement of leaked payloads,
a downloaded tool archive, or proof of security.

## How electrical computing hardware works: fundamental chain

1. **Electromagnetism**: charge, fields, conductors, resistance, reactance,
   inductance, capacitance, transient response and thermal dissipation. At
   circuit scale: Kirchhoff current/voltage laws; nodal analysis; SPICE models
   and their approximation assumptions.
2. **Device physics**: semiconductor energy bands, doped p/n junctions,
   MOS transistor gates, switching and leakage, CMOS inverter noise margins,
   threshold variability, propagation delay, parasitic capacitance and
   nonideal materials. A schematic is not a physical-device guarantee.
3. **Digital logic**: Boolean algebra, finite-state machines, flip-flops,
   metastability, resets, clock-domain crossing, setup/hold timing, power-on
   sequencing, memory coherence and bus arbitration.
4. **CPU system**: ISA-visible operations versus pipeline speculation,
   caches, MMUs/IOMMUs, page tables, DMA and interrupt/privilege logic.
   Side-channel observations depend on more state than architectural output.
5. **Firmware/ownership**: ROM → bootloader → system software; key storage,
   lifecycle fuses, secure debug availability, update signatures, anti-rollback
   checks, measurement/attestation, reset/recovery and end-of-life.
6. **Manufacturing reality**: test coverage, assembly defects, power
   integrity, heat, production variance, firmware provisioning, traceability
   and batch/lot quality. Correct high-level logic alone is insufficient.

### Printed circuit board and electronics assembly (PCB/PCBA)

- Define electrical requirements, supply voltages, current limits,
  component deratings, thermal environment and manufacturing constraints.
- Schematic capture → component selection/BOM → footprint matching →
  netlist/net connectivity → placement → stackup and controlled impedance →
  copper routing, clearances/creepage and return paths → ERC/DRC.
- Produce Gerber/ODB++ or IPC-2581 as the fabricator accepts, drill data,
  paste/stencil layers, board outline, pick-and-place and assembly drawings.
- Fabrication: laminate copper-clad substrate → expose/etch copper →
  drill/via plate → layer registration/lamination → solder mask →
  silkscreen/surface finish → electrical bare-board testing.
- Assembly: stencil solder paste → pick-and-place components →
  controlled reflow → through-hole/wave/selective solder (as needed) →
  inspection (visual/AOI, X-ray where warranted) → in-circuit/boundary-scan
  and functional end-of-line testing.
- Engineering release: lot provenance, programming fixtures, calibration,
  burn-in/stress as appropriate, quality excursions, returns and failure
  analysis. Inspection does not mathematically imply defect-free product.

Primary references:
- [KiCad file/fabrication documentation](https://docs.kicad.org/7.0/en/kicad/kicad.html)
- [IPC document revision table](https://www.ipc.org/ipc-document-revision-table)
  (standards like J-STD-001; access to full standards may be paid).
- [NIST manufacturing-sector cybersecurity profile](https://www.nccoe.nist.gov/projects/cybersecurity-framework-profile-semiconductor-manufacturing).

### Semiconductor design and fab (distinct from PCB manufacturing)

- Requirements and IP inventory → RTL or transistor-level design →
  functional simulation and formal properties → synthesis → equivalence
  checking → floorplan → placement → clock tree → routing → timing/power,
  DRC/LVS and parasitic-aware signoff → tapeout (mask design files).
- Wafer production has repeating deposition, photolithography, etch,
  implantation/doping, clean/polish and metrology stages. The *order* of
  these steps depends on the process and its qualified recipes.
- Wafer probe and characterization → dice → package/bond or flip chip →
  final automated test → firmware provisioning and lifecycle fuse burn
  (where specified) → traceability, shipping and field update/recall.
- Physical silicon is affected by process corners, coupling, defects,
  thermal limits, aging, lithography/registration error, and test coverage.
- **DRC** checks layout against design rules; **LVS** compares extracted
  connectivity with the schematic. Neither alone proves correct behavior,
  physical manufacturability, reliability or resistance to side channels.
- A **PDK** encodes foundry-specific layers, device models and constraints.
  Mixing PDK revisions invalidates otherwise plausible evidence.

Primary references:
- [NIST IR 8546 initial public draft (2025)](https://csrc.nist.gov/pubs/ir/8546/ipd)
  — silicon fabrication, packaging, tooling and cybersecurity;
  **a draft, not a finalized mandatory standard**.
- [OpenROAD open-source RTL→GDS route](https://github.com/The-OpenROAD-Project/OpenROAD)
- [SkyWater SKY130 PDK](https://github.com/google/skywater-pdk) — the
  source explicitly labels this release an **experimental preview**,
  not production qualified.
- [DARPA SSITH program](https://www.darpa.mil/research/programs/ssith) —
  hardware architectures aimed at vulnerability *classes* rather than
  exclusively patching individual software faults.

## Curated free research tools (evaluation first, install only after audit)

| Layer | Tool/source | Specific learning objective | Cheapest useful experiment |
|---|---|---|---|
| Schematic/PCB | [KiCad](https://www.kicad.org/) | ERC/DRC/netlists, Gerber, BOM and PCB stackup | design synthetic LED/resistor/sensor board; check connectivity |
| Circuits | [ngspice](https://ngspice.sourceforge.io/) | transient/AC nodal response, model fidelity | resistor ladder versus exact Fraction network |
| PCB fabrication viewers | [gerbv](https://github.com/gerbv/gerbv) | independently inspect Gerber layer output | compare schematic nets with fabricated-layer representation |
| Digital HDL | [Yosys](https://github.com/YosysHQ/yosys) | RTL synthesis and logic optimization | prove synthesized toy logic truth-table equivalence |
| Formal RTL | [SymbiYosys](https://github.com/YosysHQ/sby) | bounded property checks/counterexamples | assert debug never open in PROD |
| HDL simulation | [Verilator](https://github.com/verilator/verilator) | HDL execution, cycles, coverage, lint | cross-check finite lifecycle machine |
| Equivalence | [EQY](https://github.com/YosysHQ/eqy) | compare circuit behavior across revisions | controlled one-gate mutation |
| ASIC place/route | [OpenROAD](https://github.com/The-OpenROAD-Project/OpenROAD) | timing, layout, PDK, DRC/LVS boundary | small synthetic RTL-to-layout only, where supported |
| Open PDK | [SkyWater SKY130](https://github.com/google/skywater-pdk) | physical design constraints, version pinning | identify constraints before any fab claims |
| Custom layout | [KLayout](https://www.klayout.de/) | GDS inspection and layout rule checking | inspect self-authored square/trace geometries |
| Custom layout | [Magic VLSI](https://github.com/RTimothyEdwards/magic) | geometry/connectivity and extraction | deliberately broken trace/spacing |
| Root-of-trust | [OpenTitan](https://opentitan.org/book/doc/security/) | secure boot, lifecycle transitions, owners/creators | read-only state-model audit |
| Firmware | [NIST SP 800-193](https://csrc.nist.gov/pubs/sp/800/193/final) | protection, detection and recovery as separate guarantees | synthetic signed/unsigned update state machine |
| Reverse engineering | [Ghidra (NSA)](https://github.com/NationalSecurityAgency/ghidra) | processor semantics and decompiler/IR correspondence | compare a self-compiled binary with source |
| Architecture simulation | [gem5](https://www.gem5.org/) | modeled cache/pipeline side-effects | toy synthetic cache observations |
| FPGA/SoC | [LiteX](https://github.com/enjoy-digital/litex) | buses, registers, memory maps and peripheral integration | tiny register isolation test |
| Manufacturing lifecycle | [Tiny Tapeout](https://tinytapeout.com/) | constrained chip design/tapeout process | read submission constraints; no order placed |

Read tool license terms **per revision and dependencies** before reuse; an
open repo does not imply every artifact or bundled sample has Apache-2.0
license. Do not purchase fabrication, run hot/high-voltage equipment, or
claim a chip exists based on simulation. Avoid installing large EDA stacks
on Avrea without a measured need and the approved free budget.

## Government-developed and leaked security tools: essential distinctions

There are **three different categories**:

**A. Intentionally public defensive/research projects** — good candidates
for *authorized, pinned, license-reviewed* study.

- **SELinux**: NSA announced public Linux security enhancements in January
  2001, emphasizing type enforcement and role-based access control.
  [NSA release](https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/1637367/national-security-agency-shares-security-enhancements-to-linux/)
  Math: lattices, mandatory access-control constraints, complete mediation.
- **Ghidra**: NSA released the reverse engineering framework in March 2019,
  with public source in April 2019. Its SLEIGH architecture description and
  P-code IR give a useful *semantics/lifting* research direction.
  [NSA release](https://www.nsa.gov/Press-Room/News-Highlights/Article/Article/1775584/ghidra-the-software-reverse-engineering-tool-youve-been-waiting-for-is-here/)
  [Source-release notice](https://www.nsa.gov/Press-Room/Press-Releases-Statements/Press-Release-View/Article/1805182/attention-ghidra-users-full-source-code-released/)
  Math: architecture-to-IR semantics preservation and translation validation.
- **OpenTitan** is a consortium-led public root-of-trust project, *not a
  leaked intelligence toolkit*. [OpenTitan model](https://opentitan.org/book/doc/security/)
  Math: finite lifecycle reachability, cryptographic identity transitions,
  anti-rollback and key ownership, noninterference of debug privileges.

**B. Unauthorized disclosures of government-associated tools** —
*historical lessons*, not trusted binaries to acquire, import, execute,
or reconstruct. Attribution strength and public evidence must be separated.

- **Shadow Brokers (2016–2017)**: Microsoft investigated a public collection
  of disclosed exploits and named EternalBlue, EternalChampion and others
  alongside existing patches. Microsoft reports the Shadow Brokers as the
  leak source; assigning every file to a particular NSA operation requires
  separate evidence. See [Microsoft April 2017 assessment](https://www.microsoft.com/en-us/msrc/blog/2017/04/protecting-customers-and-evaluating-risk/)
  and [June 2017 Petya analysis](https://www.microsoft.com/en-us/security/blog/2017/06/27/new-ransomware-old-techniques-petya-adds-worm-capabilities/).
  Lessons: capability leaks amplify risk when patch deployment and network
  segmentation lag; test **synthetic** epidemic percolation/patching graphs.
  Do **not** archive or reproduce the leaked exploitation code.
- **Vault 7 (2017)**: unauthorized disclosure of CIA cyber material; DOJ
  documented the theft and criminal proceedings in 2024.
  [US DOJ release](https://www.justice.gov/archives/opa/pr/former-cia-officer-joshua-adam-shulte-sentenced-40-years-prison-espionage-and-child).
  Lessons: insider access, auditability, compartmentalization, artifact
  provenance and least-privilege release processes. No payload sourcing.
- **Equation Group**: researchers documented complex espionage tooling and
  firmware-oriented persistence claims in 2015. Attribution beyond what
  named investigators independently substantiate is not a mathematical
  proof. [Kaspersky research statement](https://www.kaspersky.com/about/press-releases/equation-group-the-crown-creator-of-cyber-espionage).
  Lessons: firmware and software trust differ; signed build chains and
  recoverable roots of trust are essential.

**C. Publicly released/leaked criminal-group software and material** —
study published *analysis* rather than deploying malware.

- **Mirai (2016)**: botnet code was made public; contemporary reporting
  details default-password vulnerabilities in embedded/IoT devices and
  copycat propagation. [Krebs October 2016](https://krebsonsecurity.com/2016/10/source-code-for-iot-botnet-mirai-released/).
  Lessons: insecure factory defaults, weak firmware update paths, device
  inventories, reliability, epidemic propagation. No malware import.
- **Conti (2021–2022)**: joint CISA/FBI/NSA/USSS advisories describe
  ransomware organization, impact and mitigations. Internal leaks reported
  elsewhere are a separate evidence class and must not be treated as
  verified first-party records. [CISA announcement](https://content.govdelivery.com/accounts/USDHSCISA/bulletins/30e2188).
  Lessons: organizational attack surfaces, permissions, business recovery,
  backup restoration and incident-response safety.

**Evidence standard:** Record whether source is an agency statement, a
vendor's observation, a third-party report, a leaked archive, or inference.
Never promote a *claim of agency origin* into verified provenance solely on
account of a filename or reputational association. Likewise, "released"
does not mean "legal to execute anywhere", and archived executable content
may itself be hostile. Downloading offensive archives offers little marginal
value for the mathematics program; focus on primary incident and defender
analysis instead.

## Systems thinking: what mathematics to extract next

| Rank | System | Invariant or optimization | Falsifier | Intended CACE / Expert Robot interface |
|---|---|---|---|---|
| 1 | **Electrical network** | Conservation: signed incidence B × branch currents = node injections | remove a trace, alter sign, short nodes | exact sparse graph Laplacian BGBᵀ, residual bounds, graph topology |
| 1 | **Manufacturing trust chain** | Each deployed device links to exact PDK, mask data, firmware and test receipt | swap BOM, source hash, PDK, test result | typed provenance/certificate graph with change impact |
| 1 | **Secure device lifecycle** | production debug access remains closed; signed update only; RMA authorization explicit | manufacturing-test flag left on | finite-state Lean proofs with independent RTL checks |
| 1 | **Trust boundary cut** | all untrusted manufacturing/programming paths intersect checked policy points | bypass edge in privilege graph | graph minimum cuts + proof of complete mediation |
| 2 | **Yield/reliability** | map process variation to failure probability with uncertainty | correlation ignored in independent defect model | interval statistics, robust constrained optimization |
| 2 | **PCB/PDK geometry** | manufacturing keep-out, spacing and via rules satisfied | inject near-miss clearance or disconnected via | computational geometry, interval clearance bounds |
| 2 | **CPU/side channels** | bounded public-observation equivalence across secret values | toy cache transient mismatch | relational Hoare logic, hyperproperties |
| 2 | **Patch propagation** | fewer reachable vulnerable devices when patch/segmentation improves | add bridge/reachability edge | monotone graph dynamics, branching processes |
| 3 | **Hardware fault tolerance** | recovery after bounded fault sequence | shared recovery path corrupted | temporal logic, error-correcting codes and state reachability |
| 3 | **Design compilation** | implementation netlist refines RTL and source semantics | optimizer changes finite truth table | proof-carrying translation/equivalence checking |

All mathematical objects are **candidate research**, not machine-verified
theorems until the Lean kernel checks exactly pinned dependencies and
assumptions. A 4-node circuit model does not validate FEM physics, fab yield,
manufacturability, or any real CPU. Each experimental output must declare
the checked domain, counterexample scope, source pin, mutation results and
whether independent CACE verification occurred.

## Immediate low-cost experiments

1. **Exact passive network conservation (no external dependencies):**
   small resistor/graph network; derive BGBᵀ with Fraction coefficients;
   apply pinned boundaries, check discrete KCL, compare to independent
   current-flow oracle; inject an open branch and a polarity/sign error.
2. **Finite silicon lifecycle model:** FAB → TEST → PROD → RMA transitions;
   reject unsigned update/debug-in-production; mutation exposes unauthorized
   transition; proof obligations for Lean/RTL.
3. **PCB clearance toy:** define two line segments and min distance as an
   exact rational inequality; distinguish touching geometries from valid
   copper clearance; no physical fabrication.
4. **Hardware/electronics provenance handoff:** input component/footprint,
   PCB/ASIC design, PDK version, firmware hash, test fixture; verify every
   artifact edge rather than merely printing a "PASS" label.
5. Use Avrea or the authorized OCI lane only when these zero-cost tests have
   generated testable qualifications needing compute; keep the existing
   fail-closed free budget and separate review branch, no paid manufacturing.

No exploit payloads, leaked offensive archives, or unauthorized target
testing are part of this research.
