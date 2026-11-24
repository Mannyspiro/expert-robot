# Linux Studio and Parallax virtual resources: initial frame

Recorded before root external source review or new trained-model experiments on
2026-11-24. Parent: MERLIN-PRODUCTION-MASTER-20261117, version 6; latest source
plan update: `20261124-studio-parallax-release-candidate`.

## Question and outcome

Can a Linux user run the pinned trained Parallax model through bounded,
application-managed RAM and a logical accelerator interface while retaining
the learned model, numerical output, source provenance, and honest reporting of
the physical execution backend? Can the completed Studio package also start
on the historically reported ARM64 target using a separately tested native build?

The intended software virtualization maps logical tensor access onto physical
file storage, bounded owned buffers, and an available processor. It does not
create additional physical RAM bandwidth, GPU cores, GPU VRAM, or CUDA support.

## Baseline and context coverage

- Source baseline: `45225d1b4c07ace715fd8be9f7dcd994e659f598`, tree
  `ccf14867c8a1b3b4aa7cc96c23bdc338f9e2ebec`, PR224, draft and unmerged.
- Existing x86_64 Studio package, actual arithmetic/stream evidence, and the
  trained CPU direct-safetensors recovery2 experiments are preserved. Their
  original protocols and receipts will not be modified or used to qualify new code.
- Current inspected source: Studio engine/server, direct loader, package/source
  plan update; RAM and GPU agents independently inspect relevant pinned modules.
- Fresh host observation: MemTotal 10,206,468 kB, MemAvailable 9,009,884 kB,
  SwapTotal 0. No nvidia-smi/rocminfo/vulkaninfo/clinfo executable, CUDA device node,
  or DRM device node was observed. This is absence in this environment, not a
  statement about the user's computer. No host swap/sysctl settings will change.
- Personal Context reports an earlier OCI ARM64 CPU-only target. This is historical
  evidence, not a new measurement or authority to alter that target.
- Standard public Ubuntu GitHub CI is authorized. No Avrea, paid compute,
  external GPU activation, OCI authority change, merge, or deployment is included.

## Premises, constraints, and observable measurements

Pinned checkpoint: YifeiZuo/Parallax-0.6B revision
`0cf73e2d49ea1a09a9ef85178b73ad68e019ae36`; 366 BF16 source tensors,
367 named parameter paths, 28 learned R and 28 R-norm tensors. Existing CPU
execution is FP32/eager, two Torch threads and one interop thread. Weight digest:
`2049f3dec8156649f1a3e2deed4decbe649cf0d7a8a9f9273453cbfa13aed2cf`.

The shared 151,936 by 1,024 embedding/output matrix alone occupies 622,329,856
bytes in FP32. An initial useful scope is selected embedding rows and tiled
output vocabulary rows, composed with existing layer weight offload. Managed
buffer bytes, staging bytes, tiles, read bytes, finite logits, greedy token IDs,
and actual backend/device identities are observable. Process RSS, allocator
caches, OS page cache, KV state, activations, returned logits and unrelated
weights must remain separately identified; a managed buffer cap is not a
whole-process or physical RAM cap.

No throughput improvement will be asserted from unmatched runs or warm-cache
timings. Physical SSD cold-cache performance and true GPU performance remain
unmeasured without suitable independent hardware evidence.

## Competing mechanisms and falsifiers

| Candidate | Predicted useful outcome | Falsifier / boundary |
| --- | --- | --- |
| Selected rows plus tiled output | Much smaller owned weight buffers with equivalent logits | Numerical tolerance, source identity, learned R, or buffer cap fails |
| Framework layer offload alone | Keeps inactive weights outside active tensors | Largest active matrix still sets a large allocation |
| OS swap or compressed swap | Larger virtual address backing | Requires host-wide changes and does not establish bounded model memory; deferred |
| Offloaded KV cache | Reduces long-context KV residency | Current short-context evidence is insufficient; deferred unless justified |
| CPU logical accelerator | Executes supported Parallax tensor operations without a GPU | Misreports CUDA/VRAM or silently accepts an unsupported requested backend |
| CUDA virtual memory / vGPU | Hardware-backed allocation or isolation | Requires physical compatible hardware/runtime; cannot qualify here |
| Graphics software renderer | Emulates graphics APIs on CPU | Does not by itself implement PyTorch CUDA/Parallax kernels; reject if no useful supported path |

This is a bounded seven-candidate mechanism review, not an exhaustive literature
search or novelty claim. All seven will receive an explicit disposition. No
claim of diversity-optimal search or global lacuna is made.

## Experiment design before execution

A separate machine-readable protocol will freeze exact experiment code,
source/input digests, prompt, dtype/thread policy, stopping limits, acceptance,
negative cases and output names before any new learned-model run. Initial
comparison is the existing five-token prompt `The capital of France is` with
prefill and three cached decode steps. Planned numerical criterion is finite
full logits, equal greedy token IDs, and allclose atol=1e-5/rtol=1e-5 against
the unchanged direct path; exact equality is reported only if observed.

Run actual model processes sequentially under the shared advisory lock
`/workspace/scratch/ba9fcb1dd88a/virtual-resource-experiment.lock` on this host.
No agent may overlap model allocations. A failed acceptance is retained;
repairs receive new source identities and an explicit protocol revision.
Pure contract fixtures may run independently but do not qualify learned-model
or hardware behavior.

## Four mathematical lenses

- **N-ality: applicable as typed independent axes.** Logical capacity, owned
  bytes, RSS, file IO bytes, physical processor type, and latency stay distinct.
  Translation-back test: receipts and UI must not collapse any into fake VRAM.
- **Simplex: not applicable to acceptance.** No convex mixture or calibrated
  probability is being estimated; normalizing resource scores adds no evidence.
- **Continuum: deferred.** A tile-budget response curve would require multiple
  predeclared measurements and error analysis; one accepted tile size does not
  qualify arbitrary sizes or smooth scaling.
- **Fuzzy logic: not applicable to gates.** Authorization, source identity,
  numerical acceptance and memory limits use explicit Boolean checks.

## Main threats and controls

Shared-agent/source correlation is disclosed; an independent verifier must
recompute output equivalence and source binding. Confirmation pressure from
the word virtualized is controlled by recording unavailable GPU results and
explicit resource scope. Warm page cache, different diagnostic overhead and
CPU scheduling prevent an unplanned speedup claim. Packaging tests cover
their actual architectures and do not imply parity with commercial assistants.

## Source ledger and remaining coverage

Initial local files read in full: `parallax_direct_disk.py`, current release
plan update. Studio engine/server are targeted partial reads sufficient for
status/endpoint integration; mutation paths will be read before editing.
Merlin skill main and all five named research/repair references were read.
Personal Context is a single bounded search for missing hardware constraints.
External primary sources and exact read coverage will be appended to a research
record, keeping this initial frame and the frozen acceptance protocol intact.
