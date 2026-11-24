# Optional local model

The source ZIP leaves this directory without model weights. The self-contained Linux Qwen1.5B profile adds its verified Qwen2.5-1.5B-Instruct Q4_K_M model as `merlin-local.gguf`, with the exact bytes recorded in `../OFFLINE_PROFILE_MANIFEST.json` and its publisher license in `../licenses/model.txt`. See [MODEL_SETUP.md](../MODEL_SETUP.md) for the profile's immutable model identity and startup instructions.

To use Studio's existing automatic local-model launcher, supply exactly one compatible `.gguf` file here and the corresponding `llama-server` distribution in `../bin/`. The launcher starts it only when no model endpoint is already configured.

For multiple models or a model elsewhere, set `MERLIN_MODEL_PATH` to the exact chosen file. No model is downloaded or chosen automatically. Select assets appropriate to your hardware and their permitted use, then verify actual conversation and tool behavior.

See [MODEL_SETUP.md](../MODEL_SETUP.md) for the complete setup. Package builds include only this README from `models/`; they never collect weights from a development machine.
