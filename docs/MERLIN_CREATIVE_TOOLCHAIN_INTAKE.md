# Merlin Creative Toolchain Intake

**Intake date:** 2026-11-15  
**Target platform:** Linux x86-64  
**Status:** source archives inspected; runtime qualification not performed

This record inventories two user-supplied archives for the Merlin creative and engineering toolchain. The archives themselves are intentionally not committed to this repository: Blender expands to approximately 1.29 GB, and executable/model assets should be distributed through an artifact store with digest verification rather than Git history.

## 1. Blender 5.3.0

- Uploaded archive: `blender-5.3.0-linux-x64.tar.xz`
- Archive size: 406,944,100 bytes
- Uncompressed member payload: 1,292,440,678 bytes
- Members: 6,672
- SHA-256: `dacb8264197a3f7fda6001285a5a506fc97ee943881261c2c3bd63c882f22e05`
- Executable: `blender-5.3.0-linux-x64/blender`
- Executable format: ELF64, little-endian, machine 62 (x86-64)
- License metadata: `license/license.md` identifies Blender as GPU-GPL 3.0 or later and documents third-party dependency licenses; `copyright.txt` is included.

The archive is structurally readable and contains no absolute or parent-traversal member paths. This is an inventory result, not a malware scan or runtime qualification.

## 2. ComfyUI source

- Uploaded archive: `ComfyUI-master.zip`
- Archive size: 13,620,522 bytes
- Uncompressed member payload: 49,925,293 bytes
- Members: 1,563
- SHA-256: `d04633f43a85041453f21c7970b4ec3881c3dd2acf4e78b535c7b44eeeeed62b`
- Project version declared in `pyproject.toml`: `0.45.0`
- Python requirement: `>=3.10`
- License file: GPL-3.0
- Git metadata: absent; the archive does not establish an upstream commit SHA.
- Custom-node files present: `example_node.py.example` and `websocket_image_save.py` (two files).
- The archive contains 133 files under `blueprints/`, including 116 JSON workflow blueprints.
- No model-weight files with common checkpoint extensions (`.safetensors`, `.ckpt`, `.pt`, `.pth`, `.gguf`, `.bin`) were found; model directories are placeholder structure/configuration only.
- These are upstream-supplied blueprints, not separately supplied user-authored workflows. Each selected blueprint still needs dependency/model review before execution.

The dependency file includes PyTorch, torchvision, torchsde and other runtime dependencies. It is not a fully pinned, target-specific environment lock. GPU/CPU execution must be qualified against the actual host and selected PyTorch build.

The archive is structurally readable and contains no absolute or parent-traversal member paths. This is not a malware scan or runtime qualification.

## 3. Architecture and runner boundary

The target for the Merlin desktop/creative runtime is Linux x86-64. The Blender executable was checked directly from the archive header and is ELF64 x86-64.

The current CACE OCI operations guide identifies its existing runner as Linux ARM64/AArch64, with labels `self-hosted,cace,oci,aarch64`. Do not run the Blender x86-64 binary on that runner. Do not silently treat an ARM64 CACE worker as the production x86-64 target. Use a qualified x86-64 worker for Blender and the canonical ComfyUI runtime; architecture-independent source inspection and tests may run elsewhere if their environment is pinned.

The Expert Robot native CI history includes a Linux x64 runner profile, but that historical CI result does not prove a currently available production runtime.

## 4. Integration design

Treat these as separate capability providers behind Merlin's capability registry:

- **Blender provider:** headless render, scene generation, geometry import/export, Python scripting, asset packaging and render-result collection.
- **ComfyUI provider:** workflow validation, model inventory, queue submission, progress/cancellation, output collection and workflow provenance.

Each job should record:
- provider and provider version;
- OS/architecture and runtime image digest;
- GPU model/driver/CUDA or CPU mode;
- Python and dependency lock digest where applicable;
- workflow/scene input digest;
- model identifiers, source and license metadata;
- seed and generation parameters where applicable;
- output artifact digests, sizes and timestamps;
- exit status, logs and resource usage.

ComfyUI model weights must be catalogued separately from the ComfyUI source. Record each model's exact upstream source, revision, digest, license/usage restrictions, required VRAM and supported workflow. Do not download or bundle arbitrary weights automatically.

All generated images, videos, Blender projects and render outputs must enter Merlin's universal artifact registry with immutable version lineage and source provenance. CACE verification should verify exact bytes and provenance; it must not claim that a successful render establishes scientific correctness.

## 5. Qualification gates

1. Preserve the original uploaded archives and verify their SHA-256 after any transfer.
2. Pin the ComfyUI upstream revision; the supplied ZIP has no Git metadata.
3. Review dependency licenses and generate a reproducible Linux x86-64 dependency lock.
4. Qualify CPU fallback first, then a separately pinned CUDA/GPU environment.
5. Run ComfyUI offline by default unless an explicitly approved provider integration is needed.
6. Test one small image workflow and one Blender headless scene/render on the actual x86-64 target.
7. Capture exact inputs, environment, outputs and resource telemetry.
8. Register both providers as `unqualified` until their exact-target smoke tests and provenance receipts pass.

## 6. Explicit non-claims

This intake does not claim that either application has been installed, launched, deployed, connected to Hermes, or qualified by CACE. No model weights, GPU compatibility, CUDA compatibility, workflow correctness or production availability is established by archive inspection alone.
