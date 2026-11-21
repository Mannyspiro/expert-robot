# Applied efficiency research for Merlin

Date: November 21, 2026, America/Phoenix.

## Implemented outcome

Two changes improve specific existing Merlin operations without changing their
required outputs: bounded-memory artifact verification and a more economical
exact rational circuit solver. The source baseline is PR187 commit
`4b1d5e75916570e0a2d37cc2371b3dc27339ad9a`. The [PR188 candidate](https://github.com/Mannyspiro/expert-robot/pull/188),
commit `45e927b7918edb7fffc3e0731c09a1df3d858866`, contains four changed
source/test files and 126 selected files overall. It is a separately reviewable
candidate; no model training, weight editing, merge or deployment occurred.

The combined local run passed **569 tests in 52.063 seconds** on x86_64 / Python
3.12.14, with 569 distinct starts and stops, zero failures/errors/skips and all
126 selected source files unchanged. Inventory SHA-256:
`4432dc519411340618c22c4c2a1ebcb756600f3ced79458a77609f51a8f9c35f`.
Source map SHA-256:
`fddded3d28afeb9494831c301b8d6254328e424d3976bffae744e1d4e865e55f`.
[Native run 44906658290](https://github.com/morganaspim/Cace-app/actions/runs/44906658290),
attempt 1, passed the same 569 software tests in 198.796 seconds on aarch64 /
Python 3.9.25, with zero failures/errors/skips, plus eight kernel and six context
cases. Actual downloaded evidence passed root and separate reviewer checks.
The four recorded service properties were unchanged. See the
[parent-linked result](../../config/merlin/plan-updates/20261121-resource-solver-native-result.json)
for exact artifact, controller, source and review identities.

This native result checks compatibility and the declared integration cases;
the operation-level performance studies below were not repeated on ARM. The
569-test unittest duration was 198.796 seconds. Subtracting that duration from
the unchanged 210-second software limit gives 11.204 seconds; this arithmetic
difference excludes setup/recording overhead and does not guarantee future
headroom. PR187's earlier 548-test run took 157.052
seconds, but the inventories and run conditions differ, so these totals do not
establish an operation-level speedup or causal regression.

## Bounded artifact-verification memory

`python/merlin/project_registry.py::verify_artifact` previously loaded the
complete file solely to hash it. The new private `_file_sha256` helper opens
fresh bytes and reads through EOF with a reusable buffer capped at 256 KiB.
The initial size selects a 4 KiB–256 KiB buffer; it never determines how many
bytes are accepted or hashed. Canonical reference/version/provenance checks
and `read_artifact_ref`'s independent final returned-byte check remain intact.

The adaptive candidate's helper body is AST-identical to the measured
prototype. Five samples per operation were retained on identical synthetic
registry bytes. These are local measurements, not whole-Merlin performance.

| Operation | Baseline peak traced allocation | Candidate peak traced allocation | Median CPU, baseline → candidate |
|---|---:|---:|---:|
| Verify 1 KiB | 8,419 B | 12,126 B | 0.216 → 0.210 ms |
| Resolve 1 KiB | 10,765 B | 14,472 B | 0.637 → 0.907 ms |
| Verify 8 MiB | 8,395,997 B | 270,228 B | 8.699 → 8.097 ms |
| Resolve 8 MiB | 8,398,343 B | 272,574 B | 8.330 → 7.938 ms |
| Verify 24 MiB | 25,173,170 B | 270,185 B | 28.233 → 23.582 ms |
| Resolve 24 MiB | 25,175,516 B | 272,531 B | 36.160 → 25.012 ms |

At 24 MiB, peak traced allocation fell approximately 98.9%. Fresh-process
observed memory high-water marks fell from 40,704 to 16,384 KiB for verification
and from 40,756 to 16,436 KiB for resolution. Traced allocation and process
high-water measurements are different quantities and are retained separately.

Small metadata resolution was slower: 1.4244 times baseline at 1 KiB and
1.2399 times at 32 KiB. Tiny-record allocation rose modestly. The earlier
fixed-buffer prototype and its small-record regression remain recorded; the
adaptive amendment was chosen after that observation. No universal latency
gain is claimed. Reading returned content still materializes the content.

Sixteen focused tests passed. The identical 8 MiB memory regression fails on
the preserved original in both verification and resolution. Four separate
review controls checked short reads and false size hints, append-after-stat,
file closure on a stat error, and same-size/same-timestamp corruption.

The registry retained **34,693,120 logical bytes before and after**. This is a
RAM improvement with no disk saving, pruning, compression or deletion.

Evidence: `verification/resource-profile/registry-streaming-20261121/` and
`verification/efficiency-continuation/registry-independent-review/`.

## Exact circuit arithmetic with less work

`python/dot_ai_os/simulation_research.py::_solve` now uses exact rational
forward elimination and back-substitution, skipping zero multipliers. It
retains pivot selection, row swaps, copied input rows, exact division and the
existing singularity error. The surrounding simulator, circuit equations,
24-part/14-net bounds, report schemas and authority flags are unchanged.

The declared comparison used 72 supported synthetic circuit specifications,
three seeds, four topology families and 0–12 unknowns. All alternatives received
the same equations and inputs. The timing harness injected each solver into
the same retained comparison implementation; the selected solver's body
matches the actual candidate AST.

| Measurement, baseline = 1 | Original | Skip zero multipliers only | Selected forward/back solver |
|---|---:|---:|---:|
| Median paired-round total solver time | 1.000 | 0.638 | 0.165 |
| Median paired-round time through retained full-comparison pipeline | 1.000 | 0.845 | 0.662 |
| Sum of per-case median peak traced allocations | 1.000 | 0.959 | 0.732 |

The selected solver required approximately 83.5% less solver time and 33.8%
less full-comparison time in that workload. Empty solves were about 0.14
microseconds slower, roughly 27%. The current fixed divider demo has one
unknown and showed no clear overall gain. Small/null/slower results remain
part of the decision rather than being removed from the sample.

All 72 cases produced equal exact `Fraction` solutions, zero independently
calculated residuals, unchanged inputs and identical complete reports.
Twenty-four additional new-seed cases passed on the actual candidate; these
are confirmation cases, not blind data. Thirteen focused test methods passed.
An arithmetic regression counts 3,588 rational operations on twelve independent
equations in the original and 12 in the candidate. Five independently prepared
full-circuit controls checked closed-form answers, separately assembled KCL,
power balance, preserved inputs, the maximum supported circuit and the
unchanged floating-island error.

The initial focused run had one incorrect new test expectation about which
existing input rejection occurs first. The preserved original confirmed the
earlier rejection. Only the new assertion was corrected; the failure and
original test bytes remain retained.

Evidence: `verification/efficiency-continuation/solver/`, including the original
frame, corpus, raw samples, decision, confirmation cases and separate review.

## What the weight-space research changes

The selected primary sources inform a bounded next experiment. They are not
Merlin measurements or a comprehensive literature review.

The original [Sparks of Weight-Space Programming][1] work gives a programmer
model access to the weights of a **separate target network**. Its reported
Qwen3.5-0.8B improvement largely repairs repeated thinking loops: MATH-500 rises
from 7.9% to 48.1% after a budget of 50 batched probes. A probe can contain many
sequences; it is not one token or one example. The non-looping Gemma 270M
experiment did not establish a math gain. This supports investigating a
specific measured bottleneck. It does not show that an inaccessible hosted
assistant can rewrite its own serving weights or gain arbitrary abilities.

[Weight-Space Programming Doesn't Need Transformers][2] supplies a useful
counterexample: the generated designs had a median GPU slowdown of 9.4 times
against their size-matched Transformer comparison. The authors' separate
associative-memory implementation achieved 7–17 times faster timing in its
bounded ARC comparison on one RTX 3090. Pretrained language models remained
more accurate. The design of the computation and memory access mattered more
than simply labeling the result a neural network or using fewer parameters.

Merlin's practical rule is to compare ordinary explicit code, a suitable
index/lookup representation and an editable network against the same original
task. Count candidate-generation calls, inference tokens, evaluator work,
wall time, memory and retention failures. A smaller model can still be slower
or less useful. Current source fixtures do not establish model-quality gain.

## Custom physics and simulated hardware

A simulation still executes on host hardware. A virtual chip described as
faster does not provide extra physical compute. A useful gain needs an explicit
translation from the original task into a cheaper computation, plus a check
that the translated result satisfies the original requirements.

The implemented exact solver is one concrete example: the physical model and
answers stay fixed while redundant arithmetic is removed. Other candidate
mechanisms include event-driven updates, symmetry/state reduction, analytical
solutions and surrogate models with declared error bounds. They are hypotheses
for a later bounded comparison, not demonstrated Merlin improvements.

For a proposed alternative physics model, record the quantities and units it
preserves, the information it discards, conversion cost, host operations and
memory, and a translation-back test. A result that is only valid under the
invented rules cannot establish a real-device capability. Reject a candidate
whose advantage disappears after conversion, checking and error correction.

The supplied YouTube Short `VyzoltTI_NA` could not be retrieved in this session.
Its contents, title and claims remain unreviewed; no decision here is attributed
to that video. A clip or transcript can supply that missing evidence later.

## Automation and next acceptance targets

These measurements were executed through retained bounded scripts against
Merlin's actual source. They do not demonstrate an unattended model-driven
research service. Reuse the existing research workflow, canonical registry and
original-task checks when connecting that service; each hypothesis still needs
a fixed budget, retained failures and an independent completion criterion.

The next model experiment remains the original-task verifier adapter described
in [APPLIED_LEARNING_RESEARCH_DECISION.md](APPLIED_LEARNING_RESEARCH_DECISION.md),
followed by an actual permitted checkpoint/runtime and disjoint development,
selection-validation and final-assessment data. The current workflow's
`holdout_passed` participates in selection, so it cannot also be reported as an
untouched final assessment. Non-RL supervised/self-supervised learning still
optimizes a declared objective; no natural desire, consciousness or biological
maternal instinct is inferred from topic selection or these engineering tests.

For disk management, the inspected registry already stores one SHA-256 blob
per distinct content digest and retains append-only artifact versions and
provenance. `MerlinReadAPI` provides current and historical views, and
`PrivateReadOnlyRegistry` can read a host-published registry snapshot. Existing
process cleanup removes its own temporary stage; it is not a retention policy
for canonical artifacts. The present experiment establishes only unchanged
disk bytes. The next narrow implementation is a bounded storage inventory in
the existing read facade: unique stored bytes, current logical-reference bytes,
historical retained bytes, version counts and physical allocation where
available. It must report truncation/unknowns and count shared digests once.
Unclassified files are not automatically reclaimable. Any collector must
identify canonical references and restore requirements before deciding that
a blob is disposable. Model caches, temporary scratch,
active experiment artifacts and retained evidence require explicit ownership
and retention rules. A read-only inventory is the next useful measurement;
automatic deletion is not implemented or authorized by this result.

The representation lenses are bounded here: n-ality separates independently
recorded task, implementation, host, budget and outcome identities; continuum
approximations are not used because the solver retains exact rational values;
simplex mixtures and fuzzy prioritization are deferred. None replaces exact
output checks. The principal remaining confounders are visible synthetic
cases, timing noise, prototype selection and workload mix. Preserved paired
samples, rejected alternatives and separately authored correctness checks
address parts of these issues without establishing broad generalization.

[1]: https://rikiyat.github.io/blog/weight-space-programming/
[2]: https://arxiv.org/html/2611.22055v1
