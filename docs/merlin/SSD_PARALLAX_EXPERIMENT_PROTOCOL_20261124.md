# SSD-backed Parallax experiment protocol

This protocol is recorded after source discovery and before running the new
implementation or benchmark. It is a component experiment, not a pretrained
model, accelerator, storage-device or deployment qualification.

## Question and fixed scope

Can a single-query, single-head Parallax decode operator use an immutable,
file-backed key/value snapshot with a bounded read buffer, preserve the resident
operator's result, and reduce the Python allocations needed to load that snapshot?

The reference is Algorithm 1 in Yifei Zuo et al., *Parallax: Parameterized Local
Linear Attention for Language Modeling*, arXiv:2605.29157v1, and the project's
`parallax/reference.py` at `987102538da4c831a0b6f2dde03ce3251182a7cf`.
This experiment implements its mathematical single-query/full-KV subset in FP64.
It is distinct from Merlin's earlier scalar local-linear sketch and from
GradientHQ's distributed inference project also named Parallax.

## Hypothesis, controls and falsifiers

- Hypothesis: resident and file-streamed executions on identical Q, R, K and V
  agree within `1e-10 + 1e-10 * abs(reference)` per output element, while the
  configured raw read buffer is independent of sequence length.
- Independent oracle: 70-digit Decimal normalized probabilities and centered
  covariance, written separately from the online four-accumulator implementation.
- Controls: zero R reduces to softmax; singleton and constant values; value and
  key translations; record permutation; non-power-of-two and multiple block sizes.
- Falsifiers: an output discrepancy above tolerance, an accepted corrupt or
  mismatched snapshot, a read exceeding its configured buffer, hidden extra full
  payload passes, or a supposedly failed gate yielding an output.
- Runtime or memory improvements are observations, not acceptance thresholds.
  Numerical stability outside these workloads is not asserted from finite inputs
  alone. Refuse nonfinite intermediate/final arithmetic.

## Workload fixed before measurement

Use deterministic generated FP64 tensors; seed and input digests accompany results.
Sequence lengths are 512, 2,048 and 8,192; key and value dimension 8; one query;
five untraced timing repetitions; file block sizes 32 and 128. Use the same
generated tensors and scale for all paths. Alternate resident/streamed call order
to reduce ordering bias. Keep generation, store construction and verification
costs visible. Do not hide them inside a claim of faster decode.

Measure resident compute with inputs already loaded, streamed compute including
open/read/hash/verification, and a resident load-plus-compute path. Measure Python
allocation peaks separately with `tracemalloc`; do not time under tracing.
Report logical input/output bytes and raw buffer capacity separately from Python
allocations. Neither measures total RSS, the kernel page cache, VRAM or physical
device memory. Do not drop caches, identify this volume as an SSD, or report
physical SSD throughput. File data may be served from a warm page cache.

## Source and execution boundaries

- File snapshots contain exactly the visible KV for one head/query. No causal
  prefix/window skipping, multi-sequence mutation, append protocol or KV reuse
  across model identities is introduced.
- Whole-file SHA-256 is supplied separately by the caller. Header and payload
  hashes are checked on the same opened descriptor in one payload pass. No output
  is returned until integrity and stable file metadata checks complete.
- A file-backed cache supplies data to real CPU arithmetic. No GPU emulation,
  trained Parallax projector, GGUF adapter, GPU kernel or token generation is
  claimed. Existing inference provider permissions remain in force.
- Learned Parallax projections require compatible trained/adapted model weights.
  Current Qwen weights cannot acquire that capability from a storage setting.

## Interpretation and next physical experiment

The decisive current comparison is resident Parallax versus the same Parallax
operator with file offload. A future model-level four-arm study (baseline, SSD
only, Parallax only, both) needs a compatible checkpoint and fixed hardware,
tokens, precision, sampling, context, batch and resource budgets. Unavailable
arms must be marked unavailable, not replaced by tensor simulations.

Resource axes are kept separate: storage capacity, working memory, read bandwidth,
compute, numerical/model quality, and execution authority. Placement fractions
are only a simplex if bytes have exactly one mutually exclusive home; duplicated
caches violate that assumption. The bandwidth/cold-bytes latency model is an
approximation requiring measurements. Fuzzy rankings cannot relax integrity,
compatibility or authorization checks.

Parent plan: `MERLIN-PRODUCTION-MASTER-20261117`, source
`6d4b5a4a3a5b81210d192554774316c04d2d88ff`, master-plan SHA-256
`7d9e5006a56a916499cb2915fcc38ac604230bf59e8b2314995c6fe884f18f9c`.
Record all outcomes, including regressions or unavailable routes, in an appended
plan event. Do not replace historical scalar or Mamba evidence.
