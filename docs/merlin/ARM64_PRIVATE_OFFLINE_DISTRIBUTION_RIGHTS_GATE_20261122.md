# Merlin private ARM64 offline AI: distribution-rights acceptance gate

**Status: OPEN / DO NOT DISTRIBUTE.** Recorded 2026-11-22. This is a technical and legal-review evidence inventory, **not legal advice or release approval**. Passing a source-only ZIP build, a private model-inclusive package integrity test, or an isolated model response is not authorization to redistribute vendor binaries or a model.

## Known exact technical inputs

| Component | Exact local SHA-256 | Source / current observed license |
|---|---|---|
| Qwen2.5-Coder-1.5B-Instruct Q4_K_M GGUF | `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` | Official GGUF repository lists Apache-2.0; pinned public license *text* SHA-256 `832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e` |
| llama.cpp `llama-server` Linux aarch64 binary | `af4c10f1f4a1e7f0878dc9b3896bb742f65170861276ef04ddecdf2a9be3cd82` | Public llama.cpp source LICENSE is MIT; pinned public text SHA-256 `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d` |
| Standalone Python 3.11.18 ARM64 interpreter | `6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c` | Extracted CPython notice at `lib/python3.11/LICENSE.txt` SHA-256 `3b2f81fe21d181c499c59a256c8e1968455d6689d269aa85373bfb6af41da3bf`; **not** complete third-party license inventory |

**Verified publisher byte provenance:** Qwen's immutable GGUF file record at commit `f86cb2c1fa58255f8052cc32aeede1b7482d4361` lists **SHA-256 `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046`**, identical to the runner's independently hashed 1,117,320,768-byte file. The official page lists Apache-2.0; a byte match does not waive notice/attribution or third-party license review.\n\n**Observed private package:** 1,150,033,739 bytes, SHA-256 `214277299d5d3b67dd8d605daab4cf900005c12af95321bca79945427903fd75`, 4,980 verified members, 3,933 safely extracted regular files, 1,049 safe symlinks. Successfully launched **packaged** CPython 3.11.18 in [OCI run #45054072040](https://github.com/morganaspim/Cace-app/actions/runs/45054072040) and the **packaged** `llama-server --version` in [OCI run #45054642914](https://github.com/morganaspim/Cace-app/actions/runs/45054642914). Neither exported the package or model weights. Native GGUF inference is a separate gate.

## Grounded publisher rights references
- Official Qwen GGUF model card: https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF (Apache-2.0). Exact license page: https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/blob/main/LICENSE
- Official llama.cpp MIT license: https://github.com/ggml-org/llama.cpp/blob/master/LICENSE
- Astral standalone Python redistribution guidance: https://github.com/astral-sh/python-build-standalone/blob/main/docs/running.rst (multiple third-party licenses, version-specific exceptions); distribution schema: https://docs.astral.sh/python-build-standalone/distributions/ (SPDX `licenses` and `license_path` metadata).

## Required before any model-containing public ZIP

1. **Model origin (byte provenance confirmed, rights review open):** the official Qwen publisher's pinned file at revision `f86cb2c1fa58255f8052cc32aeede1b7482d4361` declares SHA-256 `cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046` for `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`, exactly matching the OCI-held model. [Official upstream immutable file and Xet pointer](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/blob/f86cb2c1fa58255f8052cc32aeede1b7482d4361/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf). This closes the model **byte-to-publisher revision** link, not review of required attribution/NOTICE, modifications, trademark conditions or completed redistribution rights.
2. **Inference executable provenance:** establish an immutable llama.cpp source revision, actual build flags, linked dependencies, bundled/shared library closure and component licenses. A MIT *source* LICENSE alone does not attest the exact prebuilt binary.
3. **Standalone Python license closure:** inspect the exact Python release's embedded distribution metadata (`licenses`, `license_path` and extension-module dependencies); include all required license/notice texts, not just the CPython notice. Flag GPL-linked runtime components and historical-version exceptions. Do not infer legal compliance from a single file or project headline license.
4. **Technical platform acceptance:** real packaged Python, engine and GGUF inference; restart/readback and supported Linux ABI. Windows/macOS require their own native bundled interpreter, executable and model smoke; Linux-aarch64 technical acceptance cannot be generalized to other OSes.
5. **Release process:** independent security and legal/rights review, signed source-commit plus binary-digest provenance, explicit version and reversible installation path, and separate merge/deployment approval.

**Decisions:** keep the private model archive off GitHub artifacts and user-facing download links; export only bounded manifests/test receipts. Do not self-promote a model, assume a model LICENSE grants rights in third-party runtime components, or mark production-qualified without independent qualification.

**Associated draft reviews:** Merlin [PR #205](https://github.com/Mannyspiro/expert-robot/pull/205), CACE [PR #121](https://github.com/morganaspim/Cace-app/pull/121). This record is append-only evidence; it changes no master plan task status.
