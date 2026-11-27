# Merlin Render Lab

Render Lab extends Merlin Studio with a pinned-image QEMU launcher,
a resumable Blender frame runner, a measured worker-layout calculator,
and an editable Blender model of the workstation.

## Open-source animation stack

| Tool | Role | Qualification in this run |
|---|---|---|
| Blender and Cycles | 3D animation, Grease Pencil, compositing and scientific shots | Two actual pilot chip scenes rendered on the host |
| Inkscape | Exact vector overlays, diagrams and shot inserts | Exported the architecture SVG on the host |
| FFmpeg | Proxies, media validation and assembly | Encoded and decoded the pilot proxy on the host |
| Kdenlive and MLT | Artist-facing timeline, editing with low-resolution proxies | Kdenlive executable and MLT proxy export tested on the host |
| Krita | Painted backgrounds, texture sheets and frame-by-frame art | Documented candidate |
| OpenToonz | Traditional animation, scene exposure and batched 2D rendering | Documented candidate |
| Synfig | Interpolated vector elements and motion graphics | Documented candidate |

## Layout and evidence

Use a studio VM for Merlin/OpenBot, storyboards and proxy editing, and
assign frame rendering to host workers. Keep job receipts and durable
scene assets on a project volume. Use separate SSD scratch for the
frame cache and proxy media. A VirtIO display may support interactive
3D where the guest, host and driver stack qualify. A physical render
worker with a supported Cycles backend is the path to test for GPU
compute. Compare the same representative scenes, image quality,
memory peaks and throughput before changing backends.

On this nine-logical-CPU host, eight single-thread Blender processes
produced the highest measured batch throughput among the tested
eight-thread allocations. Use this configuration to start with similar
preview shots. Eight Blender threads were fastest for a single frame.
Eight single-thread workers completed all 24 batch frames and reached
148 verified frames/minute at the median, compared with 109 for four
two-thread workers. one eight-thread batch failed to yield one verified frame
and failed the predeclared validity gate. Sample count and ranges
are in the [evidence ledger](Findings.json).

These results apply to repeated 480 × 270 CPU previews of two pilot
chip setups. The final batch trial overlapped a separate render cache
check. An earlier guest boot attempt also overlapped the first few
batch trials. Keep the winner provisional until clean production-shot
runs with real SSD scratch, a character scene, effects and 1080p or
higher output. The per-process memory estimate excludes shared caches,
desktop activity and uncatalogued textures.

- [Raw isolated measurements](host_samples.jsonl)
- [Raw batch measurements](host_batches.jsonl)
- [Architecture diagram](layout.svg)
- [QEMU VirtIO GPU](https://www.qemu.org/docs/master/system/devices/virtio/virtio-gpu.html)
- [Blender GPU requirements](https://docs.blender.org/manual/en/latest/render/cycles/gpu_rendering.html)
- [Krita animation](https://docs.krita.org/en/user_manual/animation.html)
- [OpenToonz batch rendering](https://opentoonz.readthedocs.io/en/latest/rendering_the_animation.html)
- [Synfig command-line rendering](https://wiki.synfig.org/Render_options)
- [Kdenlive proxy media](https://docs.kdenlive.org/en/project_and_asset_management/project_settings/proxy_settings.html)

## Run it

Use Python 3.11+ on Linux. The runner needs Blender and FFmpeg. Treat
packed scene files and all explicitly listed external assets as inputs.
Only reuse a cache with the same file contents, Blender binary,
thread count and render settings.

```bash
python3 tools/merlin_studio/renderlab/render_job.py scene.blend frames \
  --frames 1 2 3 4 5 6 7 8 --workers 8 --threads 1

python3 tools/merlin_studio/renderlab/layout.py docs/merlin/studio/renderlab/host_samples.jsonl \
  --cpus 9 --reserve 1 --ram-mib 2048

python3 tools/merlin_studio/renderlab/virtual_worker.py Merlin_AI_OS_Xenomaths_x86_64.iso
```

Add `--launch` to verify the ISO digest and start QEMU. Use
`--engine kvm` only on hosts with KVM access. The default
profile uses TCG and no network or physical GPU. It leaves
the boot ISO read-only. Optional `--project-disk` takes an existing
dedicated QCOW2 project disk. Install the desired animation programs
on the appropriate worker and qualify them individually.

## Virtual worker checks

FFmpeg ran in a two-vCPU, 960 MiB QEMU TCG guest without networking
or GPU passthrough. It decoded a frame of the anime proxy and wrote an
RGB PNG. The guest used a minimal test initramfs and the Debian kernel
used by the Merlin release. Blender Cycles also rendered one pilot frame in a two-vCPU guest
with 2050 MiB. Rendering and writing the frame took 26.58 seconds
inside the guest. The PNG byte size differed from the host output.
Guest-to-host pixel equivalence remains unqualified. Smaller Blender
guest images failed during initramfs unpacking. The QEMU tests used
minimal guests, and the launcher above targets the full Merlin ISO.

To repeat the worker comparison, put the pilot's two thermal scene
files in one directory and point both benchmark commands at it.
Set `TMPDIR` to a fast local volume if you want to test its impact.

```bash
python3 tools/merlin_studio/renderlab/benchmark.py pilot-scenes isolated.jsonl
python3 tools/merlin_studio/renderlab/benchmark_batches.py pilot-scenes isolated.jsonl batches.jsonl
```
