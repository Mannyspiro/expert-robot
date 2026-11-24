# Parallax RAM and logical accelerator implementation

Parent frame: `VIRTUAL_RESOURCES_INITIAL_FRAME_20261124.md`. This record separates
implementation decisions from actual-model acceptance; the latter is recorded
by a separately frozen protocol and original output arrays.

## What is virtualized

The logical shared weight matrix still has 151,936 rows and 1,024 columns. Its
FP32 representation is 622,329,856 bytes. The new row store reads only the input
token rows for embedding lookup, then streams vocabulary-row tiles for the
output projection. It uses the same authenticated original BF16 weights,
converts each active tile to FP32 and releases its owned buffers after use.

The default is a 32 MiB budget and 4,096 rows per tile. Admission accounts for
BF16 staging, FP32 weights and the temporary projection result together:

`required_bytes = tile_rows * (1024 * 2 + 1024 * 4 + query_positions * 4)`

At the supported maximum of 64 query positions that is 26,214,400 bytes
(25 MiB). Returned full logits, embeddings, other model weights, KV cache,
activations, Python/Torch/BLAS allocation overhead and OS page cache are outside
this particular budget. Receipts report those exclusions alongside actual
owned-buffer peaks and separate process RSS. This is a bounded virtual tensor,
not an operating-system memory cap or additional physical RAM.

The logical device `merlin:software:0` executes the supported Parallax causal-LM
forward through real PyTorch CPU operations. Its separate admission policy
bounds query/context length, calls, returned logit storage and Torch threads,
allows one active forward, and rejects a session after an execution failure.
It reports `actual_device=cpu`, `hardware_acceleration=false` and
`cuda_emulation=false`. A CUDA request is explicit and must fail if unavailable
or unqualified. No requested GPU silently becomes a CPU run.

## Why this fits the actual Parallax implementation

The pinned author's `modeling_parallax.py` defines learned R projections and
R normalization in addition to Q/K/V and keeps a KV cache during decoding. The
new pager changes only embedding lookup and the tied output projection. It
does not replace attention with ordinary softmax attention, drop R, compress
the KV cache, change training, or import an optimized GPU kernel. The existing
verified layer loader continues restoring inactive weights from the original
safetensors file as needed.

Local coverage: root read the complete new row store and logical-device source,
the complete original direct loader and generation/probe code, and targeted
author attention, R and tied-head definitions. The exact checkpoint lock
authenticates both author Python files. The attempted pinned Hugging Face web
code view was unavailable; local locked source supplied the actual evidence.

## Primary research and disposition

| Mechanism inspected | Decision | Reason and source |
| --- | --- | --- |
| Selected embedding rows and tiled output | Implement and test | Addresses the largest active shared matrix without changing learned weights; pinned local author model and Torch tensor operations |
| Existing framework layer offload | Retain and compose | Accelerate moves parameters onto the execution device when used; the largest active module still matters. [Accelerate guide](https://huggingface.co/docs/accelerate/concept_guides/big_model_inference) |
| OS swap / compressed swap | Deferred | Host-wide configuration and performance differ from a narrowly owned tensor budget; no host changes are needed for this slice |
| KV cache offload | Deferred | The measured acceptance is short-context; a different long-context protocol is needed to justify its cost and benefit |
| CPU logical accelerator | Implement and test | Supported CPU operations execute the actual trained model, with explicit physical backend and bounded admission |
| CUDA VMM, Unified Memory, vGPU or MIG | Deferred pending hardware | CUDA VMM maps virtual addresses to physical memory; unified memory migrates or maps backing storage between processors. MIG partitions an existing supported GPU. [CUDA VMM](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/virtual-memory-management.html), [Unified Memory](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/understanding-memory.html), [MIG](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/introduction.html) |
| CPU graphics emulators | Rejected for this profile | A software graphics API implementation does not supply the missing qualified PyTorch CUDA/Parallax execution path; the local pinned Torch build has no CUDA support |

Coverage: seven declared mechanisms examined, two additions selected, one
existing mechanism retained, three deferred, one rejected, no duplicates,
no output-omitted or unexamined candidates inside this seven-item space.
Novelty is unknown; this is not an exhaustive research or global lacuna claim.

Root read the rendered primary CUDA VMM/Unified Memory guides, the full short
MIG introduction, targeted Accelerate inference sections and the official
Parallax repository overview. GPU-agent research has a separate source ledger.
The vGPU user-guide index was inspected only as an index, so it is not used
as detailed implementation evidence. Research date: 2026-11-24.

## Linux packaging and qualification boundaries

Studio's Qwen assistant remains independently runnable with its bundled local
runtime. Linux x86_64 and aarch64 builds use separate pinned interpreters and
native binaries. Standard public Ubuntu GitHub runners include both targets;
the [official runner documentation](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
supports this build choice. A GitHub ARM run is not a test of the user's OCI
host. The separately pinned Parallax Python/wheel kit remains Linux x86_64.

New Linux gates execute the extracted launcher, verify CPU/ABI requirements,
retain the unchanged arithmetic and actual streaming checks, and restart
the application with preserved state. The restart test found and motivated
the explicit `start_bundled_model` preference: saving the default model URL
must not accidentally turn the owned model into an externally managed one.
An explicit environment endpoint remains externally managed.

The Resource panel reads bounded kernel observations and the owned processes.
It does not infer GPU VRAM from SSD capacity or make an external model's
resource policy part of Studio's own memory budget. Live browser inspection
observed changing host available memory and Studio RSS, unavailable owned
model readings in the source preview, no observed GPU nodes, refreshed
timestamps and retained keyboard focus after refresh. No model inference
occurred during that GUI check.

## Before acceptance

Independent review identified two concrete issues before new model execution:
the imported original launcher helper needed to be in the new source hash
closure, and reference arrays needed size/layout admission before hashing or
loading. Both are new-protocol boundary requirements; the original frozen
files remain byte-identical and their historical results are preserved.

Acceptance must retain source-bound numerical outputs, R use controls,
managed allocation counts and unavailable-device/tiny-budget/token-limit
refusals. Fixture tests alone do not establish learned-model equivalence,
physical GPU availability, cold-disk performance or assistant quality.


## First actual learned-model result

Protocol `virtual-protocol-20261124.json` was frozen before execution; its
SHA-256 is `fec1bcbd80dbc38266b3b0e24c1f010ade3062be11661b36b5de04e8dc6b42d6`.
A fresh resident, fresh direct and new virtual path each produced 1,215,488
finite saved full logits for the fixed five-token prompt plus three cached
decode steps. An independent standard-library verifier read the raw FP32
arrays and found all three paths bitwise identical, maximum absolute error 0.
The separately launched CLI produced token IDs `[12095, 11, 323, 279]`, or
` Paris, and the`.

The verifier independently converted all 56 original learned R/Rnorm BF16
arrays to FP32 and matched their recorded loaded hashes. The saved R-zero
control differs by 12.764103889465332 at its maximum after FP32 rounding.
Execution receipts record all 56 R modules called four times, 367 parameter
paths back on meta after each offloaded forward and all 28 finite CPU/FP32
KV layers at sequence lengths 5, 6, 7 and 8.

The measured owned-buffer peak was 25,247,744 bytes (24.078125 MiB), below the
33,554,432-byte budget. All 160 loaded tiles were released; owned bytes were
zero after each forward. The four forwards used 152 projection tiles and
8 selected embedding rows. The separate process peaks were 4,274,511,872
bytes resident, 1,430,183,936 bytes direct and 984,190,976 bytes virtual.
Initialization contributes to these peaks; resident also executes the
R-zero control and offloaded arms retain reference arrays. They describe
this warmed-file run and are not matched-workload performance benchmarks.

Explicit CUDA, a 1 MiB budget with the 4,096-row tile, and more than 64 input
tokens each refused before creating an offload index. The logical device
reported actual CPU execution, four completed calls, no hardware acceleration
and no CUDA emulation. The source-bound independent record is
`evidence/20261124-virtual-attempt1-independent-arrays.json`.

A separate Linux review also reproduced a partial-success bug: a failed
executable hash read left an earlier compatibility field true. The producer
now revokes it; the model launcher independently requires passing status,
compatible engine, completed digest checks and matching bytes. The exact
preserved counterexample now produces zero subprocess launches. Both failed
and repaired review receipts are retained under `evidence/`.

Native packages and the final published source still require their separate
CI acceptance. This local run cannot qualify an ARM Parallax runtime, a real
GPU, the user's OCI machine or general assistant quality.
