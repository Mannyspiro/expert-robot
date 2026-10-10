# Computer-security historical casebook and systems-learning roadmap

Updated 2026-10-10. Companion to [the systems-to-mathematics atlas](computer-security-systems-history-to-mathematics-2026-10.md).

**Status:** Source-backed learning plan plus synthetic experiments. No external
targets probed; tool links are **references**, not installed dependencies;
incident descriptions follow the cited original advisories and investigator
reports. Claims about general software or actual CPU hardware need separate
qualification. Public access does not imply permission to probe systems.

## Five layers of a computing system, read from the bottom upward

1. **Physical and architectural CPU:** gates/clock, execution units, registers,
   pipelines, cache, DRAM, bus interconnect, IOMMU, interrupt controller,
   microcode/firmware, instruction-set visible state and memory order.
   Study *what the software is promised* versus what can be observed through
   cache timing, fault behavior or error propagation.
2. **Compiler and binary:** parsing/type checking → IR transforms →
   instruction selection → registers/spilling → linking and relocation →
   loading and dynamic libraries. Study semantic refinement and how a change
   can cross the source/build/package/loaded-executable boundaries.
3. **Kernel and isolation:** process identity, userspace/kernel boundary,
   page tables, privilege rings/exception levels, file descriptors, objects,
   permission checks, device drivers, boot trust roots and virtual machines.
   Ask whether *all paths* to a protected effect pass the intended policy.
4. **Network and distributed services:** TCP/IP, TLS identities, load balancers,
   shared storage, retries, idempotency, distributed consensus, failure
   detectors, queueing and propagation. Distinguish a queued job from a
   registered runner, a registered runner from executed steps, and a result
   artifact from independently verified qualification.
5. **People and institutions:** software updates, staffing, operations,
   disclosure, incentives, supply chains, software contracts and dependency
   trust. One compromise or misunderstanding can cascade across different
   companies and systems.

## Case-study ledger: real incidents, distinct mathematical questions

| Case | What the primary record establishes | Wider system interaction | Falsifiable mathematical hypothesis |
|---|---|---|---|
| Rowhammer research, 2014–2015 | [Google Project Zero](https://projectzero.google/2015/03/exploiting-dram-rowhammer-bug-to-gain.html) describes DRAM row disturbance creating cross-page bit flips | Physical DRAM faults can violate software memory-isolation assumptions; the mechanism is not just a flawed authorization check | Model fault-containment as graph reachability with bounded perturbation |
| Heartbleed, 2014 | [OpenSSL's original advisory](https://www.openssl.org/news/secadv/20140407.txt) describes excessive data exposure through heartbeat bounds handling | A protocol length field crossed into memory-copy semantics without an adequate bound | Refinement type for lengths; absence of out-of-bounds read paths |
| WannaCry, 2017 | [Microsoft's MS17-010 bulletin](https://learn.microsoft.com/en-us/security-updates/securitybulletins/2017/ms17-010) and [retrospective](https://www.microsoft.com/en-us/msrc/blog/2019/05/a-reminder-to-update-your-systems-to-prevent-a-worm) document patch availability before widespread SMB-based propagation | Attack spread depends on network connectivity, patch state, and operational patch latency | Graph epidemic thresholds, fault containment, prioritized minimum-cut immunization |
| Spectre, 2018 | [Research team](https://spectreattack.com/) distinguishes speculative side effects from architecturally committed results | CPU predictor/cache state may expose information that software control-flow reasoning misses | Two-trace noninterference under an explicitly defined observer |
| SolarWinds, 2020 | [CISA Emergency Directive 21-01](https://www.cisa.gov/news-events/directives/emergency-directive-21-01) addresses supply-chain compromise and required mitigations | A high-trust updater or management system amplifies compromise across many users | Signed provenance chains, cut-set defense, compartmentalized trust |
| MOVEit, 2023 | [NIST CVE-2023-34362](https://nvd.nist.gov/vuln/detail/CVE-2023-34362) records a pre-auth SQL injection and exploitation | Public file-transfer interface can become database authority and affect clients | Query representation refinement; capability nonexpansion under input decoding |
| 3CX, 2023 | [Mandiant's investigation](https://cloud.google.com/blog/topics/threat-intelligence/3cx-software-supply-chain-compromise) traces one compromised software installation into another supply-chain compromise | Transitive dependency trust and release channels produce an incident propagation network | Trust transitivity controls, edge provenance, observation-aware causal graphs |
| xz Utils, 2024 | [Andres Freund's disclosure](https://www.openwall.com/lists/oss-security/2024/03/29/4) describes build/release backdoor discovery | Reviewed repository sources, release artifacts and behavior diverged | Check commutation of signed source→build→release→runtime diagram |
| CrowdStrike outage, 2024 | [Vendor root cause](https://www.crowdstrike.com/en-us/blog/channel-file-291-rca-available/) documents content validation and endpoint crashes | Availability is affected by the control plane of a security product itself | Total-state contract validation; rollout safety and rollback temporal logic |

These cases are different in important ways: accidental memory safety errors,
physical effects, deliberate compromise, supply-chain attacks, operations, and
availability failures. Do not use a single "hacking cause" explanation for all.

## Further tool library (additions, not duplicated installations)

| Rank | Layer/tool | Primary upstream | Why it matters / safe cheapest first test |
|---|---|---|---|
| 1 | **herdtools7** | [herd/herdtools7](https://github.com/herd/herdtools7) | Simulate weak-memory executions from formal specifications; later compare two-thread synthetic litmus outcomes. |
| 1 | **Alive2** | [AliveToolkit/alive2](https://github.com/AliveToolkit/alive2) | Translation validation for LLVM transformations; test a tiny compiler optimization on self-authored code; note its limited interprocedural support. |
| 1 | **rr** | [rr-debugger/rr](https://github.com/rr-debugger/rr) | Deterministic record/replay for debugging race conditions; review CPU/VM prerequisites before installation. |
| 1 | **syzkaller** | [google/syzkaller](https://github.com/google/syzkaller) | Coverage-guided kernel fuzzing with manager/VM isolation; study harness design rather than run against a production host. |
| 1 | **RISC-V formal memory models** | [RISC-V unprivileged specification](https://docs.riscv.org/reference/isa/unpriv/rvwmo.html) | Distinguish permitted interleavings from a total-order assumption. |
| 2 | **OpenTitan** | [lowRISC/opentitan](https://github.com/lowRISC/opentitan) | Open silicon root of trust and verification plans; read key-lifecycle and state-machine invariants. |
| 2 | **Verilator** | [verilator/verilator](https://github.com/verilator/verilator) | Simulate and lint self-authored RTL; finite CPU pipeline toy later. |
| 2 | **Renode** | [renode/renode](https://github.com/renode/renode) | Emulate embedded boards/peripherals at the system level; isolate timing assumptions. |
| 2 | **QEMU** | [qemu/qemu](https://github.com/qemu/qemu) | Deterministic VM fixture and architecture emulation; not a substitute for real microarchitecture. |
| 2 | **Frama-C** | [frama-c](https://frama-c.com/) | C source correctness under explicit assumptions; start with bound-check contract. |
| 2 | **Valgrind** | [Valgrind](https://valgrind.org/) | Dynamic memory/instruction instrumentation on a self-owned parser fixture. |
| 2 | **Z3** | [Z3Prover/z3](https://github.com/Z3Prover/z3) | SAT/SMT constraint search and counterexample enumeration; verify solver assumptions separately. |
| 3 | **Wireshark** | [Wireshark](https://www.wireshark.org/) | Read synthetic packet captures to understand network layers, not monitor other users' traffic. |
| 3 | **Zeek** | [zeek/zeek](https://github.com/zeek/zeek) | Defensive protocol event analysis on generated PCAPs. |
| 3 | **Suricata** | [OISF/suricata](https://github.com/OISF/suricata) | Locally test rule precision on owned traffic fixtures. |
| 3 | **osquery** | [osquery/osquery](https://github.com/osquery/osquery) | Understand host-state observability and limits without collecting private host telemetry. |
| 3 | **YARA** | [VirusTotal/yara](https://github.com/VirusTotal/yara) | Deterministic matching language on hand-built inert data fixtures. |
| 3 | **Volatility 3** | [volatilityfoundation/volatility3](https://github.com/volatilityfoundation/volatility3) | Learn memory artifact analysis using generated safe dumps only. |

Tool maturity, maintainers, licenses, dependencies and platform compatibility
must be rechecked against pinned releases before import. Heavy fuzzers and
VM/hardware tools should not be installed merely because they appear here.

## What the new CPU experiment establishes—and what it cannot

Source: [synthetic CPU experiment](../scripts/experiment_toy_cpu_noninterference.py);
regression: [toy CPU tests](../tests/toy_cpu_noninterference_smoke.py).

The CPU toy has public and secret bits, a boolean speculative-branch
prediction, four observable cache lines, and 16 possible initial cache sets.
All architectural outputs equal the public bit for both secret values.
The intentionally leaky policy may leave a secret-dependent transient
cache line, so cache-set observations differ for 24/64 equal-public
execution pairs. A counterfactual *squash cache updates* model and a
constant-cache-line model each yield 0/64 mismatches in this small domain.

The experiment checks **192 two-trace comparisons** across three models
against a separate set-theoretic oracle. Neither model is evidence that real
CPUs can roll back speculative cache effects, nor evidence that constant
cache access eliminates timing leakage generally. There are no interrupts,
coherence transactions, speculative faults, timing measurements, branch
training, actual ISA instruction streams, or adversarial code executed.

**Proposed Lean statements (unproved):**

- Architectural secrecy, bounded domain:
  for any equal public input, predictor and initial cache set, the
  architectural observation is equal for both secret bits.
- Synthetic leaky-cache counterexample:
  with prediction true and empty cache, changing secret from 0 to 1
  changes the cache observation.
- Squash/constant-line cache noninterference:
  for any equal-public pair and any initial cache, the final set of cache
  lines is independent of the secret value.

Formalize the machine state as finite types and the observation as a
projection; prove by case analysis, then independently audit the Lean kernel
and axioms. CACE should consume only the resulting **explicit formal
obligations**. A Lean toy theorem cannot certify a physical chip or FEM
solver. Promotion/RSI requires separate frozen benchmarks, verified
applicability and same-or-less authority.

## Next experiments ranked by expected value per free compute minute

1. **Representation equivalence:** mutate synthetic source/package/loader
   metadata; check commuting source-to-runtime diagrams under validated
   inputs, inspired by xz and software supply chain incidents.
2. **Distributed work state machine:** build states for queued, assigned,
   executed, artifact uploaded and independently verified; search for
   forged "PASS" paths and liveness failures before attempting OCI jobs.
3. **Two-thread weak-memory litmus:** 2 loads/2 stores across two threads;
   enumerate interleavings and compare against an explicitly named memory
   model rather than inferring memory order from a programming language.
4. **Boundary-safety geometry:** encode access/authority reachability as
   graph cuts, compare greedy to exact minimum-cost guards.
5. **CACE certificate provenance:** tie sparse matrix/mesh source digest,
   independent residual, a posteriori error bound and Lean assumptions to
   one complete receipt; deliberately tamper with one input at a time.

**Acquisition policy:** primary advisory → mechanism map → falsifiable
toy → independent oracle → counterexample mutation → formally stated
claim → proof/audit → benchmark → possible promotion. Every tool,
paper and historical story remains informational input; it never changes
permissions or verification policy.
