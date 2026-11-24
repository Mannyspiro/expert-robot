# Optional local model

The source ZIP leaves this directory without model weights. The separate x86_64 and aarch64 Linux Qwen1.5B profiles add the same verified Qwen2.5-1.5B-Instruct Q4_K_M model as `merlin-local.gguf`, with the exact bytes recorded in `../OFFLINE_PROFILE_MANIFEST.json` and its publisher license in `../licenses/model.txt`. Their Python and inference binaries differ by architecture. See [MODEL_SETUP.md](../MODEL_SETUP.md) for immutable model identity, CPU/library preflight, and startup instructions.

To use Studio's automatic local-model launcher, supply exactly one compatible `.gguf` file here and the corresponding `llama-server` distribution in `../bin/`. The bundled startup preference controls whether Studio starts its own canonical loopback engine, including after a saved-settings restart. Explicit external endpoints keep their own process ownership.

For multiple models or a model elsewhere, set `MERLIN_MODEL_PATH` to the exact chosen file. No model is downloaded or chosen automatically. Select assets appropriate to your hardware and their permitted use, then verify actual conversation and tool behavior.

See [MODEL_SETUP.md](../MODEL_SETUP.md) for the complete setup. Package builds include only this README from `models/`; they never collect weights from a development machine.
