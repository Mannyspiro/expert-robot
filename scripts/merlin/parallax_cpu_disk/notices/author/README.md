---
license: apache-2.0
library_name: transformers
pipeline_tag: text-generation
tags:
- parallax
- text-generation
---

# Parallax-0.6B

Parallax (Parameterized Local Linear Attention) is an experimental language model
that reuses the Qwen3 architecture but replaces softmax self-attention with the
*parallax* op (`attn_type="parallax"`). This is the 0.6B-parameter model.

**Reference:** https://arxiv.org/abs/2605.29157

## Model details

| | |
|---|---|
| Parameters | ~0.6B |
| Layers | 28 |
| Hidden size | 1024 |
| Intermediate size | 3072 |
| Attention heads | 16 (8 KV heads, GQA) |
| Head dim | 128 |
| Vocab size | 151936 |
| Max sequence length | 4096 |
| Attention | parallax (`attn_type="parallax"`) |
| Tokenizer | Qwen3 |

## Usage

The model ships custom modeling code, so load it with `trust_remote_code=True`
(requires a recent `transformers` with Qwen3 support):

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "YifeiZuo/Parallax-0.6B"
tok = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, trust_remote_code=True)

prompt = "The quick brown fox"
ids = tok(prompt, return_tensors="pt").input_ids
out = model.generate(ids, max_new_tokens=32)
print(tok.decode(out[0], skip_special_tokens=True))
```

## License

Released under the Apache 2.0 license.
