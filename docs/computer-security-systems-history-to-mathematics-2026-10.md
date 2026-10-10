# Computer security, CPU systems, history → mathematical discovery

Evidence-led research atlas for **Expert Robot / CACE** · 2026-10-10.
Status: **reviewed references and experiment proposals**, not proof qualification,
not installed tools, not an automatic learning system, and not permission to test
internet-connected targets.

## Research protocol

Study each failure as a *system of interacting components*, not a lone bug.
Capture: who controlled each input; which representation was checked; which
component finally interpreted it; exact capability/trust boundary crossed;
observation available to a defender; relevant historical uncertainty; and a
**minimal counterexample**. Label every lesson as one of **historical report**,
**verified source behavior**, **toy experiment**, **formal theorem**, or
**deployment-qualified guarantee**. Those labels must never be conflated.

Permitted hands-on scope: offline synthetic programs, self-owned code, explicit
laboratory authorization, or public reproducible source review. No scanning,
credential access, exploit deployment, or target probing inferred from public
search indexing. Prefer zero-dependency deterministic checkers first, a pinned
toolchain second, then budget-gated Avrea and separately authorized OCI.

## How a computer actually works: relevant causal chain

**Hardware:** source language → compiler/optimizer → assembly and ABI →
instruction-set architecture (ISA) → instruction fetch/decode → register
renaming and scheduling → speculative/out-of-order execution → retirement →
memory hierarchy (registers, L1/L2/LLC, DRAM), TLB/MMU, page permissions →
kernel traps/interrupts and privilege transitions → devices via DMA/IOMMU.

ISA-visible state and *microarchitectural* state differ. A mispredicted path
may be architecturally squashed but still change caches or predictor state.
An ISA model can be functionally correct yet fail a confidentiality model
that includes observations of those structures. Such channels depend on
real CPU designs and measurement assumptions: our toy models do **not**
establish that any physical CPU is vulnerable or patched.

**Operating systems and runtime:** boot chain, firmware, hypervisor, kernel,
process/thread address spaces, virtual memory, syscalls, namespaces, filesystem
permissions, sandbox profiles, capability delegation, signals, dynamic loader,
FFI, garbage collector, allocator and memory lifetime. Ask where authority
flows, and whether every interpretation and side effect is mediated.

**Distributed systems:** packets, DNS, routing, TLS identities, request
retries, caches, distributed clocks, partial failures, durable logs, consensus,
eventual consistency and control-plane/data-plane separation. "The job was
scheduled" ≠ "a runner executed steps"; "a hash matched" ≠ "a trusted
prover ran"; "a source commit matched" ≠ "a released binary matched".
Lamport's happened-before relation is a partial order, not a global clock.

**Build and deployment:** source tree → source archive → dependency resolution →
build scripts → compiler/linker → binary/package → signer → updater →
loaded runtime. Inspect *each* transformation and representation. The
source-to-release mismatch in the 2024 xz incident is an excellent case
study for this discipline.

Hardware learning resources:
- [RISC-V RVWMO v2.0](https://docs.riscv.org/reference/isa/unpriv/rvwmo.html):
  actual model of observable load/store reorderings, dependencies and fences.
- [RISC-V formal model appendix](https://docs.riscv.org/reference/isa/unpriv/mm-formal.html):
  Alloy and formal semantics; explicit caveat on normative versus commentary.
- [CHERI introduction](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-941.html)
  and [CHERI ISAv9](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-987.html):
  bounds, permissions, tagging, provenance and authority confinement.
- [CHERI transient-execution study (2025)](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-1001.html):
  architectural capabilities alone do not settle speculative side channels.
- [gem5](https://github.com/gem5/gem5), architecture/microarchitecture
  simulator; [Spike](https://github.com/riscv-software-src/riscv-isa-sim),
  RISC-V functional ISA model. They answer **different** questions.

## Verified historical cases: incident → causal boundary → math

| Date/event | Primary evidence | Systems lesson | Candidate mathematics |
|---|---|---|---|
| 1975 protection principles | [Saltzer & Schroeder](https://web.mit.edu/saltzer/www/publications/protection/) | economy of mechanism, complete mediation, least privilege | weighted graph cuts; capability reachability |
| 1978 distributed events | [Lamport, *Time, Clocks*](https://lamport.azurewebsites.net/pubs/pubs.html) | no unique cross-node event order without communication constraints | partially ordered sets, temporal logic, vector-clock variants |
| 1988 Morris worm | [FBI historical account](https://www.fbi.gov/history/cases-and-criminals/morris-worm) | software propagation and availability collapse cross network boundaries | branching processes; epidemic threshold; fault containment |
| 2008 Debian OpenSSL RNG | [Debian DSA-1571-1](https://lists.debian.org/debian-security-announce/2008/msg00152.html) | local package change affected entropy and keys; rebuilding code is not enough if keys persist | entropy loss, min-entropy, dependency propagation |
| 2018 Meltdown/Spectre | [Discoverers' technical portal](https://www.spectreattack.com/) | architectural safety versus transient microarchitectural observation | two-trace noninterference; hyperproperties; observation equivalence |
| 2021 Log4Shell | [Apache Foundation advisory](https://news.apache.org/foundation/entry/apache-log4j-cves) | logging data crossed into lookup/execution semantics | taint flow; parser composition; privilege graphs |
| 2024 xz Utils | [Original Andres Freund disclosure](https://www.openwall.com/lists/oss-security/2024/03/29/4) | release tarball/build semantics differed from source review; anomaly detection mattered | representation equivalence, attestation chain, Bayesian evidence |
| July 2024 CrowdStrike Channel File 291 | [Vendor root-cause analysis](https://www.crowdstrike.com/en-us/blog/channel-file-291-rca-available/) | an update/content contract mismatch caused OS crashes; security tool itself became reliability hazard | interface refinement, typed schemas, fault containment, staged rollout |

These are *historical causal lessons*, not endorsements of the behavior,
public exploit instructions, or proof of generality. A nonmalicious outage
(CrowdStrike) is included deliberately: availability and update safety are
part of security engineering.

## Expanded public tools to evaluate (no installations yet)

"Evaluate" means inspect upstream sources, licenses, model assumptions and
minimum local harness cost; a name in this table does not imply the tool is
installed, permitted for all targets, trustworthy, or license-compatible
with Expert Robot's Apache-2.0 preferences. Prefer pinning upstream revisions.

| Layer | Tool/source | What to learn | Cheapest useful owned/offline evaluation |
|---|---|---|---|
| Compiler/source flow | [CodeQL](https://github.com/github/codeql) | interprocedural data-flow, sanitizers, path queries | raw-to-sink fixture; precision/recall |
| Compiler/source flow | [Semgrep](https://github.com/semgrep/semgrep) | structural patterns and guarded exceptions | seeded positive/negative Python fixtures |
| Static analysis | [Infer](https://github.com/facebook/infer) | interprocedural abstract interpretation | one simple C lifetime case |
| Model checking | [CBMC](https://github.com/diffblue/cbmc) | bounded C/C++ assertion checking | bounded buffer/index contract |
| Symbolic execution | [KLEE](https://github.com/klee/klee) | path constraints from LLVM IR | offline parser minimized witness |
| Symbolic execution | [Crucible](https://github.com/GaloisInc/crucible) | bitvector/CFG symbolic semantics and SMT | small arithmetic equivalence |
| Binary analysis | [angr](https://github.com/angr/angr) | lifting, control/data flow and symbolic states | compile tiny owned parser; compare traces |
| Reverse engineering | [Ghidra](https://github.com/NationalSecurityAgency/ghidra) | decompiler uncertainty and binary/source comparison | owned build with matching source |
| Coverage fuzzing | [AFL++](https://github.com/AFLplusplus/AFLplusplus) | feedback-guided corpus exploration | isolate toy parser, cap executions |
| Continuous fuzzing | [OSS-Fuzz](https://github.com/google/oss-fuzz) | independent oracles, sanitizer-driven triage | adapt test harness locally, not upload secrets |
| Fuzz orchestration (historical) | [OneFuzz](https://github.com/microsoft/onefuzz) | reproducible corpus/triage | concepts only; upstream archived |
| Transition systems | [TLA+/TLC](https://github.com/tlaplus/tlaplus) | crash/retry/state machine invariants | model dispatch→OCI→receipt states |
| Relational models | [RISC-V Alloy model](https://docs.riscv.org/reference/isa/unpriv/mm-formal.html) | axiomatic legal event orders | 2-core store/load litmus cases |
| Kernel correctness | [seL4](https://sel4.systems/About/FAQ.html) | proved kernel contracts and **assumption boundaries** | read/compare assurance scope |
| Hardware protection | [CHERI](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-987.html) | monotone capability authority | finite capability lattice toy |
| Microarchitecture | [gem5](https://github.com/gem5/gem5) | pipeline/cache experiments | defer heavy simulation pending model |
| ISA execution | [Spike](https://github.com/riscv-software-src/riscv-isa-sim) | ground ISA instruction semantics | tiny RV64I instruction traces |
| Proven crypto machine code | [s2n-bignum](https://github.com/awslabs/s2n-bignum) | machine-level proofs **and their assumptions** | read soundness review, no code import |
| Weakness taxonomy | [MITRE CWE Top 25 (2025)](https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25) | turn incidents into precise root-cause classes | label fixtures and negative controls |
| Prioritized incident evidence | [CISA Known Exploited Vulnerabilities](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) | real exploited versus merely hypothetical issues | source/link comparison; no scanning |

Tools formerly cataloged in [security-tool-inspiration](security-tool-inspiration.md)
remain part of the corpus. License audit is a **separate required gate**:
for example, angr advertises BSD-2-Clause and Infer MIT, but full dependency
licenses and redistribution obligations require per-version review. Never
copy attack code or public exploit payloads into the trained/offline runtime.

## System thinking: bridge to CACE and mathematical discovery

For every hypothesis, write the smallest state space, input partition,
observable output, and exact invariant. Keep independent oracle and
deliberately broken mutant. Benchmark only after passing the semantic gate.

| Priority | Cross-domain hypothesis | Finite counterexample first | Possible proof and CACE value |
|---|---|---|---|
| P1 | **Two-trace noninterference**: changing secret input leaves public observation identical | Enumerate equal-public/different-secret pairs in toy CPU with/without speculative cache updates | Relational Hoare logic / Lean theorem; choose safer caching and dataflow boundaries |
| P1 | **Representation refinement**: checked source/package/loader views agree | Mutate archive metadata and separately produced outputs | commuting diagram/equivalence proof; safer experiment and certificate intake |
| P1 | **Capability monotonicity**: every delegation grants no greater authority | generate tiny capability lattices with forged escalation edges | order theory + graph reachability; tighten Expert Robot collar |
| P1 | **Failure-safe work queues**: absent runner assignment never implies qualification | small simulated dispatch/lease/timeout/retry traces | temporal safety+liveness; correct OCI/Avrea provenance |
| P2 | **Weak-memory observations**: possible results are constrained by happens-before and fences | 2-thread litmus on tiny finite state; reject invented x86 assumptions | partial orders and SAT/SMT; concurrent sparse solver consistency |
| P2 | **Minimum complete mediation**: guard set intersects every untrusted-input→sink path | bounded graph counterexamples to first-path greedy | min cut, dual optimization; reduce defense cost without losing coverage |
| P2 | **Entropy budget**: cryptographic key quality is bounded by effective source entropy | toy biased RNG, no production key generation | information theory; avoid false-confidence model uncertainty |
| P3 | **Reliability under rollout**: faults should be localized and detected before broad deployment | finite staged update system with malformed schema | fault-tree/probabilistic model checking; rollback and deployment gates |
| P3 | **Certificate chain soundness**: numerical receipt matches originating code, parameters and result | alter hash, module, timing, source/derived artifact one at a time | dependent type/proof-carrying data; residual certificate integrity |

Realized mathematics must be distinguished from **conjectures**. A proved
statement about a bounded toy model does not prove equivalent security on
actual Intel/Arm/RISC-V hardware, a live kernel, or CACE's PDE solution.
To strengthen CACE numerics, tie any optimization to exact operator inputs,
mesh topology, residual bounds, a posteriori estimators, interval bounds
and blind-mesh non-regression.

### Practical initial sequence (ranked by information gained per free minute)

1. Implement an exact, finite **two-trace noninterference** experiment
   (synthetic CPU architecture versus toy speculative cache observation),
   prove every enumerated pair with an independent oracle and a deliberate
   counterexample; run locally (no dependencies).
2. Convert the invariant into a Lean statement with explicit finite traces,
   disallowing new axioms/sorry; label as *not proved* until exact kernel replay.
3. Apply the same two-trace technique to Expert Robot's
   candidate permissions, CI receipt boundary, and parser policy.
4. Check archive/source representation equality on the authorized CACE OCI
   bridge, without leaking deploy keys or relaxing its Avrea budget.
5. Benchmark proof-aided pruning/canonicalization in CACE's geometry or
   sparse operators against independently verified residual certificates.

### Data hygiene and provenance

Maintain a small table for each later ingestion: URL, author/institution,
event date, date retrieved, primary/secondary distinction, claimed behavior,
observational uncertainty, license, SHA if downloaded, and proposed falsifier.
No browser page, external model, incident story, GitHub README, archived tool,
or proof-looking JSON gains implementation authority. Future code from these
sources must pass the existing GitHub branch review and trusted verification
gates; never widen auto-promotion scope by treating learning as permission.
