# Third-party notices for Merlin integrations

This file records the initial licensing basis for optional model integrations. Recheck upstream license files and voice-pack terms before redistribution.

| Component | Upstream | License reported upstream | Notes |
|---|---|---|---|
| Hermes Agent | https://github.com/NousResearch/hermes-agent | MIT | Source is installed separately under `.tools/`. |
| NousCoder-14B weights | https://huggingface.co/NousResearch/NousCoder-14B | Apache-2.0 | Model card identifies Apache-2.0. |
| NousCoder GGUF conversion | https://huggingface.co/bartowski/NousResearch_NousCoder-14B-GGUF | Apache-2.0 | Community conversion of NousResearch weights; Q4_K_M is ~9 GB. |
| Kokoro ONNX runtime | https://github.com/thewh1teagle/kokoro-onnx | MIT | Optional Python dependency. |
| Kokoro-82M weights | https://huggingface.co/hexgrad/Kokoro-82M | Apache-2.0 | Keep license/notice material with redistributed weights. |

No attribution line is required in the generated WAV output under the listed model/runtime licenses. This is not a blanket statement about all possible voice packs or training-data components: review the selected voice pack's current terms and retain upstream notices for redistributed assets.
