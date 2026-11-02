# Merlin / Hermes coding and local voice integration

## What this adds

- Hermes Agent source checkout in `.tools/hermes-agent` (not committed as vendored code).
- NousCoder-14B as an optional coding model, served by `llama-server` through a local OpenAI-compatible endpoint.
- Kokoro-82M ONNX as an optional local TTS engine, exposed at `http://127.0.0.1:8880/v1/audio/speech`.
- No model weights, audio samples, API credentials, or runtime caches are committed to Git.

The existing Qwen3-Coder role remains unchanged. NousCoder is an additional specialist and must be benchmarked against the existing coder before any default-role change.

## Hermes Agent source

```bash
scripts/install_hermes_agent.sh
# Optional: also run the upstream user-level installer
scripts/install_hermes_agent.sh --install
```

The source checkout is placed in `.tools/hermes-agent`. The Avrea acquisition workflow clones this source and records the exact upstream commit in its short-lived provenance artifact. Record the local revision with:

```bash
git -C .tools/hermes-agent rev-parse HEAD
```

The upstream project is MIT-licensed. Review its current install script and dependency changes before upgrading.

## NousCoder-14B

The official NousResearch NousCoder-14B model is Apache-2.0 and is a 15B-parameter BF16 checkpoint. This integration uses the community GGUF conversion from `bartowski/NousResearch_NousCoder-14B-GGUF`, also marked Apache-2.0.

Default quantization: **Q4_K_M (~9 GB)**. The downloader verifies SHA-256 `9cc51afc755319db42a6324baf3395436cce5954dc87df95d3b9e7d625610624` against the published file metadata. This is intentionally not checked into Git. The download is opt-in:

```bash
scripts/models/download_nouscoder.sh
```

Install a current `llama.cpp` build, then start the local model server:

```bash
scripts/models/run_nouscoder.sh
```

Defaults are loopback-only (`127.0.0.1:8080`) and 65,536 context tokens. A 9 GB weight file plus a 64K context requires substantial RAM; use a host with adequate free memory. Reduce `CTX_SIZE` only if the connected agent does not require 64K context. Hermes Agent's current quickstart documents 64K as its minimum context requirement.

Configure Hermes Agent to use the local endpoint:

```bash
hermes config set model.provider custom
hermes config set model.base_url http://127.0.0.1:8080/v1
hermes config set model.default bartowski/NousResearch_NousCoder-14B-GGUF:Q4_K_M
```

The coding agent must still operate through Expert Robot's bounded tools and sandbox; installing Hermes does not grant it repository, filesystem, network, or credential authority.

## Local Kokoro voice

Kokoro is an 82M-parameter TTS model. The ONNX runtime package is MIT-licensed and the model weights are Apache-2.0. Apache-2.0 does not require an attribution line in generated audio; retain the applicable license and notice files when redistributing model assets. Voice-pack and dataset provenance should be rechecked before shipping bundled voices.

Download model and voice assets (about 300 MB combined):

```bash
scripts/models/download_kokoro.sh
scripts/models/run_kokoro.sh
```

Health check:

```bash
curl http://127.0.0.1:8880/health
```

Speech request:

```bash
curl -X POST http://127.0.0.1:8880/v1/audio/speech \\
  -H 'Content-Type: application/json' \\
  -d '{"input":"Merlin council is ready.","voice":"af_heart","response_format":"wav"}' \\
  --output council.wav
```

The server binds to loopback by default, does not log speech text, and has no external service dependency. The initial MVP supports English voices (`en-us`, `en-gb`) and WAV output. Council playback can consume the returned WAV bytes sequentially; browser autoplay still requires a user gesture in many browsers.

## Verification and rollout gates

1. Run `python3 -m unittest discover -s tests/voice -v`.
2. Run `bash -n scripts/install_hermes_agent.sh scripts/models/*.sh`.
3. Download model assets only on a machine with sufficient disk and memory.
4. Smoke-test `/health` and a short speech generation.
5. Benchmark NousCoder against the existing Qwen3-Coder on a fixed, held-out coding set.
6. Keep Hermes Agent behind the existing sandbox/tool-broker permissions.
7. Do not promote a new default model or expand authority based on a successful install alone.

## Upstream references

- NousCoder-14B: https://huggingface.co/NousResearch/NousCoder-14B
- GGUF conversion: https://huggingface.co/bartowski/NousResearch_NousCoder-14B-GGUF
- Hermes Agent: https://github.com/NousResearch/hermes-agent
- Kokoro ONNX runtime: https://github.com/thewh1teagle/kokoro-onnx
- Kokoro model: https://huggingface.co/hexgrad/Kokoro-82M
