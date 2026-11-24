"""Parallax HF config (inherits Qwen3Config).

Parallax (Parameterized Local Linear Attention) reuses the Qwen3 architecture
and swaps softmax self-attention for the parallax op. This config inherits from
``transformers.models.qwen3.configuration_qwen3.Qwen3Config`` so it picks up all
of Qwen3's conventions for free (strict dataclass, ``rope_parameters``,
``layer_types``, tp/pp plans, etc.).

The only Parallax-specific addition is the ``attn_type`` field, which selects the
attention implementation. When ``attn_type == "sdpa"`` this config describes a
plain Qwen3-equivalent model.

Reference: https://arxiv.org/abs/2605.29157
"""

from __future__ import annotations

from transformers.models.qwen3.configuration_qwen3 import Qwen3Config


class ParallaxConfig(Qwen3Config):
    r"""Config for the Parallax model (Qwen3-derived).

    Args:
        attn_type (`str`, *optional*, defaults to `"parallax"`):
            Attention implementation. Must be one of ``"sdpa"`` or
            ``"parallax"``. ``"sdpa"`` uses the plain Qwen3 causal attention
            path (softmax attention). ``"parallax"`` uses the parallax op and
            requires the extra ``r_proj`` / ``r_norm`` per-layer weights.
    """

    model_type = "parallax"

    # ---- Parallax-specific extra ----
    # "sdpa"    : plain causal self-attention (identical to Qwen3).
    # "parallax": the parallax op (adds r_proj + r_norm and replaces softmax
    #             self-attention).
    attn_type: str = "parallax"

    def __post_init__(self, **kwargs):
        if self.attn_type not in ("sdpa", "parallax"):
            raise ValueError(
                f"attn_type must be 'sdpa' or 'parallax', got {self.attn_type!r}"
            )
        super().__post_init__(**kwargs)


__all__ = ["ParallaxConfig"]
