# Bounded logical CPU execution for Parallax

## Decision and experiment frame

The executable first slice uses the installed PyTorch CPU runtime to perform the
trained Parallax model's operations. A logical device admits a bounded request,
checks the actual inputs and returned tensor storage, executes the CPU forward,
and reports the real device. It composes with the separately reviewed managed
embedding/output-row implementation. CUDA requests refuse before model loading;
there is no implicit fallback and no GPU acceleration claim.

The question is whether this bounded software execution and row paging preserve
the trained model's outputs while reducing the largest transient weight buffer.
The baseline is the source-verified direct-file CPU loader at commit
`45225d1b4c07ace715fd8be9f7dcd994e659f598`, with the same learned R projections,
original BF16 checkpoint, FP32 computation, eager attention and raw tokenizer.
Observable outcomes are full finite-logit agreement, exact greedy tokens, active
R observations, real staging-buffer measurements, actual device receipts, and
rejection of requests outside the supported profile.

No model experiment is implied by the capability observation or small fixtures.
The new combined protocol must be frozen before the resident, direct and virtual
model processes run. Earlier Parallax protocols and evidence remain unchanged.
The full learned-model result belongs to that new protocol and its actual arrays.

## Hardware and software alternatives

| Candidate | Primary-source result | Decision for this profile |
| --- | --- | --- |
| CUDA virtual memory management | Address reservation, physical allocation, mapping and access are distinct operations. Device support is queried explicitly. Reserved addresses do not provide physical backing or compute. | No CUDA runtime or GPU is available locally. No VMM implementation is claimed. |
| CUDA Unified Memory | Actual CPU/GPU memory can participate in managed addressing and migration. Supported access and oversubscription depend on the platform and device capabilities. | It cannot make a CPU-only runtime execute CUDA kernels. No OS paging or VRAM-size claim. |
| NVIDIA vGPU or MIG | These share or partition supported physical GPU resources and require the appropriate hardware, drivers and platform configuration. | Hardware qualification remains a prerequisite. No host, hypervisor or licensing changes. |
| Software graphics backends | LLVMpipe and SwiftShader execute supported graphics APIs on CPUs. Their existence does not establish a PyTorch operator or learned-model adapter. | The installed Vulkan loader alone is insufficient. No backend rebuild or blind driver installation. |
| PyTorch CPU operations | The existing model already executes through verified CPU PyTorch, including learned Parallax R projections. | Implement this actual software path with explicit resource admission and device reporting. |

The local observation found CPython 3.11.18 and Torch 2.9.1+cpu; CUDA was neither
built nor available and Torch's Vulkan availability query returned false. The
selected NVIDIA, DRM and ROCm device nodes and command-line tools were absent.
A Vulkan loader library was discoverable, while the inspected
`/usr/share/vulkan/icd.d` directory yielded no ICD manifests. This is bounded
local capability coverage, not a survey of every possible software driver.

## Implemented contract

`parallax_virtual_device.py` exposes `ExecutionLimits`, `select_backend`, and a
`LogicalAccelerator` with `forward`, `descriptor` and `snapshot` methods. The
supported operation is a batch-one, unpadded, cached FP32 causal-LM forward on
CPU. Defaults admit at most 64 query tokens, 80 total context tokens, 16 forward
calls, two Torch threads and 40 MiB of returned logit backing storage per call.
Limits may be tightened. They cannot be increased beyond this profile.

Admission validates CPU input IDs and masks, vocabulary bounds, cache devices
and shapes, model parameter/buffer devices, context length and predicted output
bytes. A call then executes under Torch inference mode. Actual returned logits
must have the admitted shape, finite FP32 CPU values, and both logical and
backing-storage bytes within the cap. A small view into a larger allocation is
therefore rejected. Cache and model devices are checked after execution as well.

Only one call may be active in a session. An admission error leaves it reusable;
an execution or result error poisons it because cache state may already have
changed. CPU receipts identify `merlin:software:0`, `pytorch_cpu`, actual device
`cpu`, and `hardware_acceleration: false`. A detected GPU would still be
unqualified for this CPU-specific row-paging implementation; availability alone
does not pass a model acceptance test.

These are separate accounting scopes:

- The RAM manager bounds the live BF16 staging, converted FP32 weight rows and
  temporary projection-result tiles it owns.
- The logical executor bounds each returned logit tensor's backing storage and
  request dimensions. It does not bound outputs retained by a caller later.
- Whole-process RSS, other layer weights, KV, activations, runtime libraries,
  allocator arenas and OS cache remain separately observed or excluded.

The abstraction does not implement CUDA/PTX emulation, virtual GPU hardware,
KV paging, OS swap control, a system-wide memory quota, or a speed guarantee.

## Validation design and failure evidence

`parallax_virtual_probe.py` adds a new source-bound trial without editing the
original probe. Resident mode reuses the immutable original runner; direct and
virtual modes reuse the unchanged direct loader and step algebra, with a new
bounded reference reader. Virtual mode additionally composes the managed loader
and logical CPU executor. Every
actual model process holds the same exclusive advisory lock. The launcher uses
separate sequential processes with constructed offline environments and at most
two CPU threads.

The predeclared input is `The capital of France is`, with one prefill and three
cached decode forwards. Acceptance requires all full saved logits to be finite
and satisfy `atol=rtol=1e-5`, exact greedy IDs, 56 R/Rnorm modules observed on CPU
four times, 367 meta parameter paths after each offloaded forward, valid CPU FP32
KV shapes and lengths, no copied `.dat` weights, and managed current bytes zero
after each forward with peak bytes at or below the declared budget. A fresh
resident R-zero control establishes that learned R affects this computation.

The bounded CLI then generates four tokens using the same fixed input. CUDA,
tiny-budget and oversized-prompt requests must fail before an offload index is
created. A diagnostic cannot rescue a failed numerical criterion. Failures retain
their stage, error, source/protocol hashes and any arrays already produced.

Reference receipts and arrays are admitted through one regular, nonsymlink,
bounded and stable descriptor before their bytes are hashed. The safetensors
header must describe exactly the fixed four FP32 shapes and contiguous payload
ranges before tensor loading. Matching hashes do not authorize a larger input.

The launcher retains a known log for each child, capped at 128 KiB while hashing
the observed complete stream, and kills the child process group on timeout.
Small independent-process fixtures check truncation, termination and advisory
locking; small real Torch fixtures test CPU arithmetic and execution boundaries.
These fixtures load no learned checkpoint.

Resident work additionally includes the R-zero forward, while direct and virtual
work retain reference arrays. Timing and RSS therefore describe these processes;
they do not establish an equal-workload speed comparison. Complete source hashes
also warm the filesystem, so neither physical SSD throughput nor cold-cache
performance is measured.

## Primary sources and read coverage

Sources were consulted on 2026-11-24. Mutable documentation is identified as
such; none is an unpinned runtime dependency. The runtime remains the existing
hashed Torch 2.9.1+cpu / Transformers 5.6.2 / Accelerate 1.16.0 closure.

| Primary locator | Coverage used |
| --- | --- |
| [CUDA VMM programming guide](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/virtual-memory-management.html) | Device capability query, reservation without physical allocation, mapping and access sections; current mutable guide. |
| [CUDA memory concepts](https://docs.nvidia.com/cuda/cuda-programming-guide/02-basics/understanding-memory.html) | Unified addressing/system memory concepts and platform-dependent support; current mutable guide. |
| [CUDA driver virtual-address API](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__VA.html) | Search coverage of allocation/mapping API distinctions; not a full API review. |
| [CUDA driver memory API](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MEM.html) | Search coverage of managed-memory oversubscription and concurrent-managed-access prerequisites; not a full API review. |
| [MIG prerequisites](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/getting-started-with-mig.html) | Prerequisites and GPU/compute-instance setup sections; no configuration performed. |
| [vGPU installation and configuration](https://docs.nvidia.com/vgpu/19.0/grid-vgpu-user-guide/installing-configuring-grid-vgpu.html) | vGPU architecture and prerequisite sections for the 19.x documentation family. |
| [PyTorch 2.9 backend capabilities](https://docs.pytorch.org/docs/2.9/backends.html) and [CUDA availability](https://docs.pytorch.org/docs/2.9/generated/torch.cuda.is_available.html) | Distinction between CUDA build support and actual current availability. |
| [PyTorch 2.9 module hooks](https://docs.pytorch.org/docs/2.9/generated/torch.nn.Module.html) | Forward/pre-forward hook semantics; the new executor adds no competing weight-residency hooks. |
| [Mesa LLVMpipe](https://docs.mesa3d.org/drivers/llvmpipe.html) | Introduction and requirements of the CPU software rasterizer. |
| [SwiftShader official README](https://github.com/google/swiftshader/blob/master/README.md) | Introduction and Vulkan usage; mutable master, not installed or executed. |
| [PyTorch Vulkan workflow](https://docs.pytorch.org/tutorials/unstable/vulkan_workflow.html) | Maintenance warning and custom-build requirement. This does not qualify an adapter for the pinned model. |

Local code coverage included the complete direct loader, original probe and
replay, the current RAM manager and root-owned virtual CLI, and the new device,
probe and replay sources. Project navigation included `docs/merlin/README.md`,
the SSD/Parallax integration and recovery records. This lane does not claim to
have re-read every historical production-plan task.

## Reasoning lenses and remaining boundary

The useful analogy is virtual address translation plus bounded tensor staging:
the application can present a large logical tensor while loading small concrete
pieces. The resource-conservation check keeps arithmetic on an actual processor
and distinguishes address space, storage capacity and compute throughput.
Dimensional checks separate element counts from backing bytes and managed bytes
from whole-process RSS. A negative-control lens requires unavailable CUDA,
unaffordable tiles, oversized output storage and excess context to refuse before
useful work can be misreported. An evidence-coverage lens keeps graphics-driver
availability separate from a supported PyTorch/model adapter.

The remaining GPU boundary is explicit: actual compatible hardware/runtime,
an audited model adapter and new full-logit/resource acceptance are required
before this profile can report GPU execution. No remote endpoint or historical
ARM64 host is activated by this implementation.
