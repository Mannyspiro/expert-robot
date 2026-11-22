# Merlin Linux offline AI ZIP profile v1

**Status: deterministic packaging candidate; not a qualified release.** The builder targets Linux x86-64 and Linux aarch64. Windows/macOS require separately qualified interpreters, inference runtimes, extraction formats and startup tests.

## What the profile contains

The original Merlin Studio source ZIP is extended with explicit, locally supplied, source-pinned assets:

| Path under Merlin_Studio | Contents |
| --- | --- |
| runtime/python/ | Relocatable Python 3.10+ interpreter, standard library, native extension binaries and safe symlinks |
| bin/llama-server | Target-specific Linux ELF64 llama.cpp inference server |
| models/merlin-local.gguf | One explicitly selected GGUF model |
| licenses/model.txt, licenses/inference.txt, licenses/python.txt | Full source-preserved licenses/notices for the exact selected assets |
| PROFILE_VERIFY.py, OFFLINE_PROFILE_MANIFEST.json | Independent profile verifier and complete extra-file hash inventory |

The base package manifest is preserved, and the profile adds a second explicit allowlist with SHA-256, byte counts, POSIX modes, fixed archive timestamps and source-publisher declarations. The builder requires exact externally provided SHA-256 for Python, llama-server and GGUF, checks ELF target architecture and GGUF magic, rejects unbounded or unsafe path/symlink input, independently verifies the final ZIP, and never downloads files or installs on the host. It cannot certify source authenticity, external licensing, transitive system library ABI or model quality.

## Asset sources and legal review

The official Qwen2.5-Coder-1.5B-Instruct-GGUF repository (https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF) includes an Apache 2.0 LICENSE. llama.cpp (https://github.com/ggml-org/llama.cpp) lists an MIT license. python-build-standalone (https://github.com/astral-sh/python-build-standalone) provides redistributable prebuilt CPython distributions. A license file's presence **does not prove the selected binary was built from that source or that distribution rights have been reviewed**; inspect all notices and transitive libraries. CI does not upload model weights or user state.

## Build with already supplied local inputs

First independently compute the SHA-256 hashes of every input, preserve source and licensing receipts, and choose assets matching the same architecture. The Python root must be an extracted relocatable installation containing bin/python3.

~~~sh
python3 portable/build_portable.py --output /work/Merlin-Studio.zip
python3 scripts/verify_portable.py /work/Merlin-Studio.zip

python3 portable/build_offline_profile.py \
  --studio-zip /work/Merlin-Studio.zip \
  --python-root /work/python-standalone/python \
  --python-sha256 YOUR_VERIFIED_PYTHON_EXECUTABLE_SHA256 \
  --llama-server /work/llama-server \
  --llama-sha256 YOUR_VERIFIED_LLAMA_SERVER_SHA256 \
  --gguf-model /work/qwen-coder.gguf \
  --gguf-sha256 YOUR_VERIFIED_MODEL_SHA256 \
  --model-license /work/licenses/QWEN_LICENSE \
  --inference-license /work/licenses/LLAMA_LICENSE \
  --python-license /work/licenses/PYTHON_LICENSE \
  --target linux-x86_64 \
  --model-origin https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF \
  --inference-origin https://github.com/ggml-org/llama.cpp \
  --python-origin https://github.com/astral-sh/python-build-standalone \
  --output /work/Merlin-Studio-linux-x86_64-offline-model.zip
~~~

Use linux-aarch64 and its exact verified binaries on ARM64. A 1.5B Q4 model typically exceeds 1 GiB, so allow substantial disk space and validate all archive members before extraction.

~~~sh
python3 scripts/verify_offline_profile.py /work/Merlin-Studio-linux-x86_64-offline-model.zip
unzip -q /work/Merlin-Studio-linux-x86_64-offline-model.zip -d /work/test-install
/work/test-install/Merlin_Studio/runtime/python/bin/python3 \
  /work/test-install/Merlin_Studio/PROFILE_VERIFY.py \
  /work/Merlin-Studio-linux-x86_64-offline-model.zip
cd /work/test-install/Merlin_Studio
./START.sh
~~~

Use Linux unzip that preserves executable bits and safe relative symlinks. Studio's START.sh prefers the embedded Python interpreter and serves the offline UI on loopback port 8771. With no saved model endpoint, the separately supplied llama-server is started on loopback port 8772 with the model alias local. If an optional binary fails to launch, the offline workspace must remain usable. Source package manifests do not cover user-created files after extraction.

## What has actually been tested

GitLab pipeline 3099814498 passed **six synthetic packaging fixtures plus four bundled launcher fixtures**. The fixtures test reproducibility, model byte tampering, executable CPU mismatch, unsafe symbolic links, unknown archive members, missing licenses, restart and safe fallback when the optional model cannot start. Later fixtures also test zero-length Python metadata files. They use tiny fake ELF/GGUF headers, not real compiled interpreters or model weights.

The separate native OCI Qwen/Studio run 45034470736 established actual model replies and restart on the integrated source, **not** from this new combined ZIP. Before calling any asset-packed ZIP fully usable, independently demonstrate executable/ABI startup, actual GGUF mapping, real tool calls, public/private network boundaries, restart, runtime/cost constraints, offline extraction, end-user state migration and rollback. Sign and publish only after license review and independently approved release authority.

The profile manifest deliberately states: authenticity_verified=false, license_review_completed=false, native_executable_started=false, production_qualified=false.
