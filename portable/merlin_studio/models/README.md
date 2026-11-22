# Optional local model

This directory intentionally contains no model weights.

To use Studio's existing automatic local-model launcher, supply exactly one compatible `.gguf` file here and the corresponding `llama-server` distribution in `../bin/`. The launcher starts it only when no model endpoint is already configured.

For multiple models or a model elsewhere, set `MERLIN_MODEL_PATH` to the exact chosen file. No model is downloaded or chosen automatically. Select assets appropriate to your hardware and their permitted use, then verify actual conversation and tool behavior.

See [MODEL_SETUP.md](../MODEL_SETUP.md) for the complete setup. Package builds include only this README from `models/`; they never collect weights from a development machine.
