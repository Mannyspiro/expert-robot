"""Parallax HF modeling file (inherits from Qwen3).

Parallax (Parameterized Local Linear Attention) reuses the Qwen3 architecture
and only overrides the attention class to swap softmax self-attention for the
parallax op (``attn_type="parallax"``).

Reference: https://arxiv.org/abs/2605.29157

Design notes
------------
* All boilerplate — RMSNorm, MLP, rotary embeddings, decoder-layer scaffolding,
  the base ``PreTrainedModel`` class, ``Qwen3Model``, ``Qwen3ForCausalLM``,
  mask preparation, cache handling, ``GenerationMixin`` integration, etc. —
  is inherited from ``transformers.models.qwen3``.
* The only new code is:
    - ``parallax_forward``: a pure-PyTorch kernel implementing the parallax op,
      batched over heads and taking an additive attention mask in the HF shape
      ``(B, 1, q_len, kv_len)``.
    - ``ParallaxAttention``: inherits from ``Qwen3Attention``, adds an
      ``r_proj`` / ``r_norm`` pair when ``config.attn_type == "parallax"``,
      and overrides ``forward`` to dispatch to ``parallax_forward`` in that
      case. For ``attn_type == "sdpa"`` the forward simply delegates to
      ``Qwen3Attention.forward`` unchanged, so all modern HF attention
      backends (sdpa, flash_attention_2, flex_attention, eager) remain
      available for that path.
    - ``ParallaxDecoderLayer``, ``ParallaxModel``, ``ParallaxPreTrainedModel``,
      ``ParallaxForCausalLM``: thin subclasses that rewire parent classes to
      the ``ParallaxAttention`` / ``ParallaxConfig`` below.
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
from transformers.cache_utils import Cache
from transformers.models.qwen3.modeling_qwen3 import (
    Qwen3Attention,
    Qwen3DecoderLayer,
    Qwen3ForCausalLM,
    Qwen3Model,
    Qwen3PreTrainedModel,
    Qwen3RMSNorm,
    apply_rotary_pos_emb,
    repeat_kv,
)

from .configuration_parallax import ParallaxConfig


# ---------------------------------------------------------------------------
# Parallax op (pure PyTorch)
# ---------------------------------------------------------------------------


def parallax_forward(
    module: nn.Module,
    query: torch.Tensor,
    r: torch.Tensor,
    key: torch.Tensor,
    value: torch.Tensor,
    attention_mask: Optional[torch.Tensor],
    scaling: float,
    dropout: float = 0.0,
    **kwargs,
) -> tuple[torch.Tensor, None]:
    """The parallax op.

        p = softmax((Q Kᵀ) * scale + mask)
        rk = R Kᵀ
        s = p V
        c = sum(p * rk, -1, keepdim=True)
        r_term = (p * rk) V
        out = s + c * s - r_term

    Shapes
    ------
    query : (B, H, q_len, D)
    r     : (B, H, q_len, D)          — Parallax-specific extra projection
    key   : (B, H_kv, kv_len, D)      — GQA-compressed, expanded internally
    value : (B, H_kv, kv_len, D)
    attention_mask : (B, 1, q_len, kv_len) additive, 0 or -inf (HF convention)

    Returns
    -------
    attn_output : (B, q_len, H, D)    — transposed to match Qwen3 eager impl
    attn_weights : None               — not exposed (the parallax op has no
                                         meaningful "attention matrix" per head)
    """
    # Expand GQA-compressed k/v to match q heads
    key = repeat_kv(key, module.num_key_value_groups)
    value = repeat_kv(value, module.num_key_value_groups)

    # Upcast to float32 for numerical stability (the softmax accumulates in fp32).
    out_dtype = query.dtype
    qf = query.float()
    rf = r.float()
    kf = key.float()
    vf = value.float()

    qk = torch.einsum("bhqd,bhkd->bhqk", qf, kf) * scaling
    q_len = qk.shape[-2]
    kv_len = qk.shape[-1]
    if attention_mask is not None:
        # HF causal masks may cover a larger key span than our current
        # kv_len during decode; slice to match.
        qk = qk + attention_mask[..., :q_len, :kv_len].to(qk.dtype)
    elif q_len > 1:
        # HF's `create_causal_mask` returns None when the model's default
        # attention backend (e.g. sdpa) handles causality implicitly. The
        # parallax op is hand-written and needs the explicit additive mask,
        # so build one here. Decode (q_len == 1) is naturally unmasked: the
        # single query can attend to every cached key.
        offset = kv_len - q_len
        row = torch.arange(q_len, device=qk.device)[:, None] + offset
        col = torch.arange(kv_len, device=qk.device)[None, :]
        causal = row >= col
        bias = torch.zeros(q_len, kv_len, dtype=qk.dtype, device=qk.device)
        bias = bias.masked_fill(~causal, float("-inf"))
        qk = qk + bias

    p = torch.softmax(qk, dim=-1)
    rk = torch.einsum("bhqd,bhkd->bhqk", rf, kf)

    s = torch.einsum("bhqk,bhkd->bhqd", p, vf)
    c = (p * rk).sum(dim=-1, keepdim=True)
    r_term = torch.einsum("bhqk,bhkd->bhqd", p * rk, vf)

    attn_output = (s + c * s - r_term).to(out_dtype)
    # Match Qwen3 eager_attention_forward: return transposed (B, q_len, H, D)
    attn_output = attn_output.transpose(1, 2).contiguous()
    return attn_output, None


# ---------------------------------------------------------------------------
# Attention / DecoderLayer / Model / ForCausalLM
# ---------------------------------------------------------------------------


class ParallaxAttention(Qwen3Attention):
    """Qwen3 attention plus an optional parallax path."""

    def __init__(self, config: ParallaxConfig, layer_idx: int) -> None:
        super().__init__(config, layer_idx)
        self.attn_type = config.attn_type
        if self.attn_type == "parallax":
            # Extra projection + RMSNorm for the parallax op.
            self.r_proj = nn.Linear(
                config.hidden_size,
                config.num_attention_heads * self.head_dim,
                bias=config.attention_bias,
            )
            self.r_norm = Qwen3RMSNorm(self.head_dim, eps=config.rms_norm_eps)

    def forward(
        self,
        hidden_states: torch.Tensor,
        position_embeddings: tuple[torch.Tensor, torch.Tensor],
        attention_mask: Optional[torch.Tensor],
        past_key_values: Optional[Cache] = None,
        **kwargs,
    ) -> tuple[torch.Tensor, Optional[torch.Tensor]]:
        if self.attn_type != "parallax":
            # Plain Qwen3 attention — delegate to the parent, which supports
            # sdpa / flash_attention_2 / flex_attention / eager backends.
            return super().forward(
                hidden_states=hidden_states,
                position_embeddings=position_embeddings,
                attention_mask=attention_mask,
                past_key_values=past_key_values,
                **kwargs,
            )

        # ---- Parallax path ----
        input_shape = hidden_states.shape[:-1]
        hidden_shape = (*input_shape, -1, self.head_dim)

        query_states = self.q_norm(
            self.q_proj(hidden_states).view(hidden_shape)
        ).transpose(1, 2)
        key_states = self.k_norm(
            self.k_proj(hidden_states).view(hidden_shape)
        ).transpose(1, 2)
        value_states = self.v_proj(hidden_states).view(hidden_shape).transpose(1, 2)

        # r: same num_heads as q (not num_key_value_heads), rope applied.
        # Note hidden_shape uses -1 for the heads dim, so r_proj (which produces
        # num_attention_heads*head_dim) will correctly view as (..., n_heads, D).
        r_states = self.r_norm(
            self.r_proj(hidden_states).view(hidden_shape)
        ).transpose(1, 2)

        cos, sin = position_embeddings
        query_states, key_states = apply_rotary_pos_emb(
            query_states, key_states, cos, sin
        )
        r_states, _ = apply_rotary_pos_emb(r_states, r_states, cos, sin)

        if past_key_values is not None:
            key_states, value_states = past_key_values.update(
                key_states, value_states, self.layer_idx
            )

        attn_output, attn_weights = parallax_forward(
            self,
            query_states,
            r_states,
            key_states,
            value_states,
            attention_mask,
            dropout=0.0 if not self.training else self.attention_dropout,
            scaling=self.scaling,
        )

        attn_output = attn_output.reshape(*input_shape, -1).contiguous()
        attn_output = self.o_proj(attn_output)
        return attn_output, attn_weights


class ParallaxDecoderLayer(Qwen3DecoderLayer):
    def __init__(self, config: ParallaxConfig, layer_idx: int) -> None:
        # Call the grandparent (nn.Module) init to avoid Qwen3DecoderLayer
        # building a Qwen3Attention we'd immediately replace.
        nn.Module.__init__(self)
        self.hidden_size = config.hidden_size
        self.attention_type = config.layer_types[layer_idx]
        self.self_attn = ParallaxAttention(config=config, layer_idx=layer_idx)
        # Reuse the MLP + norms from Qwen3 via its own constructor logic.
        # Easiest is to rebuild them directly here to match Qwen3DecoderLayer.
        from transformers.models.qwen3.modeling_qwen3 import Qwen3MLP

        self.mlp = Qwen3MLP(config)
        self.input_layernorm = Qwen3RMSNorm(config.hidden_size, eps=config.rms_norm_eps)
        self.post_attention_layernorm = Qwen3RMSNorm(
            config.hidden_size, eps=config.rms_norm_eps
        )


class ParallaxPreTrainedModel(Qwen3PreTrainedModel):
    config: ParallaxConfig  # type: ignore[assignment]
    config_class = ParallaxConfig
    base_model_prefix = "model"
    _no_split_modules = ["ParallaxDecoderLayer"]
    # The parallax path is hand-written and does not plug into
    # ALL_ATTENTION_FUNCTIONS. The sdpa path (delegated to super) supports the
    # standard backends.
    _supports_flash_attn = True
    _supports_sdpa = True
    _supports_flex_attn = True


class ParallaxModel(ParallaxPreTrainedModel, Qwen3Model):
    def __init__(self, config: ParallaxConfig) -> None:
        # Bypass Qwen3Model.__init__ (which builds Qwen3DecoderLayers) and
        # rebuild the module tree with ParallaxDecoderLayers.
        Qwen3PreTrainedModel.__init__(self, config)
        self.padding_idx = config.pad_token_id
        self.vocab_size = config.vocab_size
        self.embed_tokens = nn.Embedding(
            config.vocab_size, config.hidden_size, self.padding_idx
        )
        self.layers = nn.ModuleList(
            [
                ParallaxDecoderLayer(config, layer_idx)
                for layer_idx in range(config.num_hidden_layers)
            ]
        )
        self.norm = Qwen3RMSNorm(config.hidden_size, eps=config.rms_norm_eps)
        # Qwen3Model constructs its rotary embedding from the config; reuse.
        from transformers.models.qwen3.modeling_qwen3 import Qwen3RotaryEmbedding

        self.rotary_emb = Qwen3RotaryEmbedding(config=config)
        self.gradient_checkpointing = False
        self.has_sliding_layers = "sliding_attention" in (config.layer_types or [])
        self.post_init()


class ParallaxForCausalLM(ParallaxPreTrainedModel, Qwen3ForCausalLM):
    _tied_weights_keys = {"lm_head.weight": "model.embed_tokens.weight"}

    def __init__(self, config: ParallaxConfig) -> None:
        # Bypass Qwen3ForCausalLM.__init__ (which builds a Qwen3Model) and
        # rebuild with ParallaxModel.
        Qwen3PreTrainedModel.__init__(self, config)
        self.model = ParallaxModel(config)
        self.vocab_size = config.vocab_size
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        self.post_init()


__all__ = [
    "ParallaxAttention",
    "ParallaxDecoderLayer",
    "ParallaxForCausalLM",
    "ParallaxModel",
    "ParallaxPreTrainedModel",
    "parallax_forward",
]
