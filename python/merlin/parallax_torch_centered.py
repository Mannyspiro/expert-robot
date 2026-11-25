"""One inference-only centered FP32 covariance candidate for a pinned Parallax LM.

This optional module requires PyTorch. It performs no model load, networking,
training or global patching. The caller explicitly installs/restores this
function in an isolated evaluation process after source and protocol review.
"""
from __future__ import annotations

import math
import torch


def _repeat_kv(states, groups):
    if groups == 1:
        return states
    batch, heads, sequence, dim = states.shape
    return states[:, :, None, :, :].expand(batch, heads, groups, sequence, dim).reshape(batch, heads * groups, sequence, dim)


def centered_parallax_forward(module, query, r, key, value, attention_mask,
                              scaling, dropout=0.0, **kwargs):
    """Retain QK/RK, GQA and causal semantics; change only moment reduction.

    With mass m=sum(p), mean_a=sum(p*a)/m, the exact normalized output is
    ((p @ V) - (p * (a-mean_a)) @ V) / m. The explicit denominator avoids
    asserting that rounded softmax entries sum to one in exact arithmetic.
    This first pilot accepts FP32 projection inputs only. No FP64
    preconditioning or learned parameter modification occurs. For rounded
    softmax mass unequal to one, this explicitly normalized expression differs
    from the author's fixed-p expression; the full-logit gate measures that
    approximation rather than claiming bitwise or formal FP32 equivalence.
    """
    if module.training or dropout != 0:
        raise ValueError("candidate is restricted to dropout-free inference")
    if not torch.is_inference_mode_enabled() or torch.is_autocast_enabled("cpu"):
        raise ValueError("candidate requires inference_mode with CPU autocast disabled")
    if query.device.type != "cpu" or any(x.device != query.device for x in (r, key, value)):
        raise ValueError("this reviewed candidate is CPU-only")
    if any(x.dtype != torch.float32 for x in (query, r, key, value)):
        raise ValueError("this first pilot requires FP32 Q/R/K/V")
    if query.ndim != 4 or r.shape != query.shape or key.ndim != 4 or value.shape != key.shape:
        raise ValueError("bounded compatible Q/R/K/V tensors required")
    batch, heads, q_len, dim = query.shape
    kv_len = key.shape[-2]
    groups = module.num_key_value_groups
    if (batch != 1 or not 1 <= q_len <= 129 or not q_len <= kv_len <= 129
            or not 1 <= heads <= 16 or not 1 <= dim <= 128
            or type(groups) is not int or groups < 1 or key.shape[0] != batch
            or key.shape[1] * groups != heads or key.shape[-1] != dim
            or not isinstance(scaling, (int, float)) or not math.isfinite(scaling) or scaling <= 0):
        raise ValueError("candidate exceeds the frozen one-window evaluation scope")
    out_dtype = query.dtype
    qf, rf = query.float(), r.float()
    kf, vf = _repeat_kv(key, groups).float(), _repeat_kv(value, groups).float()
    qk = torch.einsum("bhqd,bhkd->bhqk", qf, kf) * scaling
    if attention_mask is not None:
        # Preserve the author's larger-span slicing without permitting
        # broadcasting to silently expand any frozen B/H/Q/K dimension.
        if (attention_mask.ndim != 4 or attention_mask.device != query.device
                or attention_mask.dtype != torch.float32
                or attention_mask.shape[0] != batch
                or attention_mask.shape[1] not in (1, heads)
                or attention_mask.shape[2] < q_len
                or attention_mask.shape[3] < kv_len
                or attention_mask.shape[2] > 129 or attention_mask.shape[3] > 129):
            raise ValueError("bounded FP32 additive mask required")
        if bool(torch.isnan(attention_mask).any()) or bool(torch.isposinf(attention_mask).any()):
            raise ValueError("additive mask contains NaN or positive infinity")
        qk = qk + attention_mask[..., :q_len, :kv_len].to(qk.dtype)
    elif q_len > 1:
        row = torch.arange(q_len, device=qk.device)[:, None] + kv_len - q_len
        col = torch.arange(kv_len, device=qk.device)[None, :]
        qk = qk.masked_fill(row < col, float("-inf"))
    p = torch.softmax(qk, dim=-1)
    a = torch.einsum("bhqd,bhkd->bhqk", rf, kf)
    mass = p.sum(dim=-1, keepdim=True)
    mean_a = (p * a).sum(dim=-1, keepdim=True) / mass
    mean_value_numerator = torch.einsum("bhqk,bhkd->bhqd", p, vf)
    covariance_numerator = torch.einsum("bhqk,bhkd->bhqd", p * (a - mean_a), vf)
    output = (mean_value_numerator - covariance_numerator) / mass
    if not bool(torch.isfinite(output).all()):
        raise ValueError("candidate produced nonfinite attention output")
    return output.to(out_dtype).transpose(1, 2).contiguous(), None
