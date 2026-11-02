# NousCoder-14B qualification record — 2026-11-02

## Acquisition

- Model: NousResearch/NousCoder-14B
- Quantized file: NousResearch_NousCoder-14B-Q4_K_M.gguf
- GGUF source: bartowski/NousResearch_NousCoder-14B-GGUF
- Size: 9,001,754,752 bytes
- SHA-256: 9cc51afc755319db42a6324baf3395436cce5954dc87df95d3b9e7d625610624
- Acquisition and checksum verification: passed on Avrea 8-vCPU runner
- Model cache: saved in Actions cache; weights are not committed to Git

## Runtime

- llama.cpp CPU server built successfully on Avrea.
- Context configured to 65,536 tokens.
- The NousCoder model config declares 81,920 maximum positions with YaRN scaling (factor 2.0, original 40,960), so the selected 65,536 context is within the published configuration.
- Hermes Agent source commit: 5e7c2b254d414e4e25105231f818f385fee67469

## Inference qualification

The first chat-completion request used the model's default reasoning mode and returned an empty visible content field. A raw completion produced reasoning text but stopped before a complete function. Those results are not accepted as a coding pass.

The current qualification request disables Qwen3 thinking through chat_template_kwargs.enable_thinking=false, sets reasoning_format=none, and requires the response to contain both a complete function definition (def clamp) and a return statement. Only that stricter result can qualify the model for the coding adapter.

This is a single smoke test, not a benchmark. Promotion still requires a fixed held-out coding set, correctness checks, tool-use discipline, resource measurements and comparison against the existing Qwen3-Coder role.
