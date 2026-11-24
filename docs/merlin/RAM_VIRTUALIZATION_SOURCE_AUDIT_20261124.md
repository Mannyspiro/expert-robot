# RAM virtualization source audit and implementation checkpoint

Parent: [initial frame](RAM_VIRTUALIZATION_INITIAL_FRAME_20261124.md), preserved
before external research. Existing plan parent:
[`20261124-studio-parallax-release-candidate`](../../config/merlin/plan-updates/20261124-studio-parallax-release-candidate.json),
under canonical master plan v6. The master plan is referenced, not reread or
replaced here; no whole production task is marked complete. Root owns the
combined virtual-resource protocol, integration and eventual publication.

## Primary-source coverage

| Source identity | Read coverage and finding | Limits |
| --- | --- | --- |
| Author checkpoint `YifeiZuo/Parallax-0.6B`, revision `0cf73e2d49ea1a09a9ef85178b73ad68e019ae36` | Complete local `modeling_parallax.py` and the current verified direct-loader/support source. R projections, normalization, rotary position embeddings, attention formula and K/V cache are reused unchanged. The tied source is a `[151936,1024]` BF16 embedding matrix. | This is source inspection, not a new inference result. Original acquisition/weight identity remains bound by the existing checkpoint lock. |
| Installed Accelerate 1.16.0 `hooks.py`, 34,802 bytes, SHA-256 `17fc87337d3c027a46ca8accfbc915053134d0399d37885a0ca59afd4fd47928` | Relevant `add_hook_to_module`, `remove_hook_from_module`, `AlignDevicesHook` initialization and `detach_hook` code. Detach restores weights only for non-meta original devices. | The new loader requires the exact ordinary `AlignDevicesHook`, `offload=True` and original weight device meta before removing either large module's hook. Other hook shapes refuse. |
| Installed Accelerate 1.16.0 `utils/offload.py`, 8,351 bytes, SHA-256 `6fab55c19b05ad18bbdc0f0f561fdd338ee5edd28b7ff6913c1901d30157440d` | `OffloadedWeightsLoader` construction and complete `__getitem__` path. Existing safetensors retrieval loads a complete tensor then converts its dtype. | This explains a complete FP32 matrix materialization; it does not measure total RSS or storage-device speed. |
| Installed Transformers 5.6.2 `models/qwen3/modeling_qwen3.py`, 23,353 bytes, SHA-256 `fbdcfeeb1b54135ca67ba7df924da92f4b264e1252b517eea2de989289ebaeab` | Complete `Qwen3ForCausalLM` forward. It calls the normal embedding module and later `lm_head` on the selected hidden positions. | The new provider supports CPU FP32 inference, batch one and at most 64 positions in a forward. It does not support training or arbitrary model families. |
| [Accelerate 1.16.0 API documentation](https://huggingface.co/docs/accelerate/v1.16.0/en/package_reference/big_modeling) | Relevant empty-weight, disk-offload and hook API sections. Cross-checked the behavior against the actual pinned installed source above. | The attempt to read the pinned GitHub hooks page through the web tool returned a fetch-disabled result. No remote full-file read is claimed. |
| [PyTorch 2.9 `torch.frombuffer`](https://docs.pytorch.org/docs/2.9/generated/torch.frombuffer.html) | Complete relevant API description: CPU buffer sharing, explicit dtype and retained owner lifetime. | Only CPU bytearrays are passed. Inference-only execution and nonescaping tile consumers prevent autograd or callers from retaining a managed tile. |

The installed dependency files come from the previously verified 39-wheel CPU
closure. The current upstream documentation is not substituted for those exact
installed source identities. No new package was installed for this work.

## Implemented slice

New module: `scripts/merlin/parallax_cpu_disk/parallax_virtual_memory.py`.

```python
validate_budget(managed_bytes, tile_rows)  # pure stdlib, before model/source access
model, provenance, manager = load_ram_managed(
    checkpoint, index_dir, managed_bytes=32 * 1024**2, tile_rows=4096
)
# Model inference is performed by the separately bounded execution provider.
state = manager.snapshot()
# Check original source provenance before this final cleanup.
manager.close()
```

The manager streams selected embedding rows and output-head vocabulary tiles
from the complete-hash-verified source descriptor. It interprets offsets from
that same descriptor, not a separately trusted metadata path. Both module
parameters remain meta, retaining the 367-path inventory. Other weights still
use the original verified offloader; the attention and cache code is untouched.
There is no second weight dump, persistent resident weight cache, OS swap change,
GPU implementation or model-file rewrite.

For a tile with `R` rows, hidden width `C=1024`, and `Q` query positions, the
explicit simultaneous buffers are:

```
BF16 staging       2 * R * C bytes
FP32 weight        4 * R * C bytes
projection result  4 * Q * R bytes
total              R * (6 * C + 4 * Q) bytes
```

At the supported maximum `Q=64`, a 4,096-row tile requires 26,214,400 bytes
(25 MiB), below the default 32 MiB managed budget. This is a data-storage
budget for those buffers, **not a process-memory cap**. Full returned logits,
embeddings, other model weights, K/V, activations, JSON metadata, Python/runtime
overhead, allocator caches, BLAS workspace and OS page cache are excluded and
remain explicit in every snapshot. Full source hashing uses a separate bounded
staging phase included in the manager's counters; it never maps the whole file.

In exact arithmetic, selecting embedding rows and partitioning the output
matrix by its vocabulary rows preserves each output dot product. FP32 kernel
selection can still change rounding; only the future frozen full-model
comparison can establish numerical acceptance for the tested workloads.

## Actual verification so far

Thirteen targeted CPU fixture cases passed, zero skipped, in 2.497 seconds.
They use small artificial BF16 tensors and the real pinned Torch/Accelerate
implementations, not trained-model inference. The result and exact source
hashes are retained in
[`virtual-memory-fixture-validation.json`](../../scripts/merlin/parallax_cpu_disk/evidence/virtual-memory-fixture-validation.json)
and its complete bounded test log.

Checks include a subprocess proving that budget preflight imports no Torch,
budget refusal before `load_direct`, exact selected rows with duplicates,
tiled-versus-dense projection including a final partial tile, weak references
showing that weight/result tile objects do not escape, actual storage counters,
changed/incorrect/symlink/truncated source refusals, invalid device/dtype/layout
and grad-mode refusals, kernel/read fault cleanup, close/reuse behavior,
overlapping-operation refusal, constructor descriptor cleanup, and an offload
map that raises if hook removal tries to load the full weight.

Original direct-loader/support/probe sources and both recovery2 protocols were
compared byte-for-byte with published `45225d1`; they are unchanged. There has
been **no new trained-model run or RSS/speed result** at this checkpoint. Root
will freeze the combined numerical protocol before resident/direct/managed
processes execute sequentially under the shared resource lock.

## Decision and next discriminating observation

Proceed to the combined bounded learned-model comparison. Keep the same model,
precision, workload, source identities and output retention across direct and
managed runs. Require finite complete logits and matching greedy tokens within
the predeclared tolerance, all learned R observations, all 367 meta parameters
after forward, zero live managed buffers between calls, and actual RSS/USS/peak
RSS reported separately. Preserve failures and revise source/protocol only after
diagnosis. A smaller managed counter alone cannot establish physical RAM savings.
