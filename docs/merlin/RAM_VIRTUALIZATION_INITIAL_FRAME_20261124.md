# Initial RAM virtualization frame — 2026-11-24

Status: proposed, before external primary-source research and before model execution.
Parent source: `45225d1b4c07ace715fd8be9f7dcd994e659f598`, tree
`ccf14867c8a1b3b4aa7cc96c23bdc338f9e2ebec`. This extends the existing
Parallax CPU disk profile; it is not another registry or a replacement for
the canonical plan. Root owns integration and the next frozen protocol.

## Question and observable target

Can a bounded application-level virtual tensor store reduce the largest
temporary weight working set during execution of the actual trained Parallax
checkpoint, while preserving its numerical outputs and learned R path?
Measure managed buffer bytes, source bytes read, page/tile activity, finite
logit errors, greedy tokens, process RSS/USS/peak RSS and elapsed time separately.
Do not equate a managed allocation budget with total process or OS memory.

## Existing observations and premises

- Observed source: the current direct loader constructs 367 FP32 meta parameter
  paths and asks Accelerate to retrieve complete parameter tensors from the
  exact BF16 safetensors checkpoint. The output head aliases the input embedding.
- Observed checkpoint shape: that shared matrix has 151,936 rows by 1,024
  columns. One complete FP32 materialization is 622,329,856 bytes; its original
  BF16 storage is 311,164,928 bytes. This arithmetic is not a measured process peak.
- Observed previous acceptance: the existing direct-file profile executed the
  real model and matched the resident reference for one prefill and three decode
  steps. Those frozen source/protocol/receipts remain unchanged.
- Observed source: learned R, Q/K normalization, RoPE, causal masking and ordinary
  per-layer K/V cache are in the pinned author model. K/V and activations remain
  CPU tensors; the attention implementation forms full score tensors per layer.
- Reported current host limits from root: about 10.2 GB memory, no swap and no
  CUDA device. No sysctl/swap changes, new hardware, paid runtime or remote dispatch.
- Assumed until tested: row-select embedding and tiled output projection can
  preserve numerical results within a predeclared tolerance. Different matrix
  kernel shapes may change FP32 rounding even when the mathematical map is exact.

## Competing mechanisms and smallest proposed slice

1. Page the tied embedding/output-head tensor and run the output projection in
   bounded vocabulary-row tiles. This directly addresses the largest known
   materialization and can reuse the exact checkpoint without rewriting weights.
2. Page historical K/V between layers. This directly bounds cache residency but
   gives a smaller effect for the current short-context profile and still requires
   each active layer's attention inputs unless the attention kernel is tiled.
3. Enable OS swap or claim GPU emulation. Excluded: outside authorized scope and
   does not establish bounded model arithmetic or additional physical compute.

Preferred first slice is (1), contingent on exact pinned hook/API review. A new
module would install bounded embedding and head forwards over the existing
verified direct loader. The original matrix remains represented by meta
parameters; its logical identity and tied source are preserved. Other modules
continue using the already accepted offloader. K/V, returned logits, activations,
runtime allocations and OS page cache must be explicitly outside this weight
buffer budget. A later cache-paging step requires a separate decision and proof.

## Proposed interface and constraints

`load_ram_managed(checkpoint, index_dir, *, managed_bytes, tile_rows)` returns
`(model, provenance, manager)`. `manager.snapshot()` reports actual managed
current/peak bytes, read bytes, pages/tiles and evictions if a cache is used.
It must refuse invalid budgets before allocation, wrong shape/dtype/device,
altered source identity and unsupported model modes. Each claimed budget counts
both source BF16 staging and converted FP32 buffers, not merely parameter metadata.
No shared integration surface is edited until root agrees to this contract.

## Acceptance frame before the frozen protocol

Use the same trained checkpoint/runtime and two CPU threads. Compare the
existing direct-file baseline and the managed variant in separate fresh
processes with identical workload, precision and output retention. Keep the
original short acceptance as one workload; root will choose any additional
bounded workload, exact tolerance and stopping rule before execution. Preserve
all full output arrays and failures. Require finite logits, matching greedy
tokens, learned R execution, correct tied-source rows, and all parameters meta
after forward. A budget below the required working tile must fail before loading
weights; active allocation counters must be independently checked against actual
tensor/buffer lengths. Do not infer broad model quality or physical SSD speed.

Every actual model process must hold the shared exclusive advisory lock at
`/workspace/scratch/ba9fcb1dd88a/virtual-resource-experiment.lock`. Announce the
bounded run first. No concurrent RAM/GPU-lane model runs.

## Lenses, bias controls and decision changes

- Simplex: deferred; no mixture optimization is needed for this exact tensor map.
- N-ality: applied; correctness, managed bytes, process memory, I/O and elapsed
  time are independent acceptance axes, never one synthetic success score.
- Continuum: not applicable to the initial discrete page/row implementation.
- Fuzzy structures: not applicable to integrity, resource budgets or numerical
  acceptance, which remain explicit gates.
- Anchoring risk: previous RSS savings could bias toward another positive claim.
  Countermeasure: equal-workload fresh-process comparisons, record null/regressive
  RSS results, and retain source/cache warmth limitations.
- Metric substitution risk: meta parameters or a small managed counter may hide
  other allocations. Countermeasure: report exclusions plus actual RSS/USS and
  verify staged BF16, FP32 and temporary tile allocations separately.
- Change the design if hook removal materializes the full matrix, numerical
  tolerance fails, source identity is weakened, or a required temporary exceeds
  the declared managed budget. Preserve that failure before revising the protocol.

## Append-only update 1 — implementation and fixture checkpoint

Root approved mechanism (1). The exact pinned Accelerate hook source confirms
that detaching an original-meta weight need not restore it. The new module
enforces that condition and retains both original meta parameters. The public
preflight is named `validate_budget`; defaults are 32 MiB and 4,096 vocabulary
rows. Accounting was made more conservative by including the temporary
projection-result tile, giving a worst-case 25 MiB requirement at 64 positions.
Source offsets are derived from the same fully hashed descriptor used for rows.

The first bounded fixture run passed 13 cases with no failures or skips. No
trained-model inference occurred. See the [source audit and checkpoint](RAM_VIRTUALIZATION_SOURCE_AUDIT_20261124.md)
for exact source coverage, test identities, exclusions and the next acceptance.
The initial premises and competing mechanisms above are preserved; K/V paging
remains deferred and no new physical-memory claim is made.
