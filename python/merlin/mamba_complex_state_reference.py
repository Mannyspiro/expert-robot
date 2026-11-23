"""Mathematical complex-state recurrence reference inspired by Mamba-3 ideas.

This is NOT the Mamba-3 discretization, MIMO parameterization, CUDA kernel,
trained model or inference benchmark. It demonstrates the classical stable
complex recurrence / explicit history identity in a simulated state carrier.
"""
from __future__ import annotations

import cmath
import math

MAX_SEQUENCE = 2048


def _validate(values, retention, angle):
    if not isinstance(values, (list, tuple)) or not 1 <= len(values) <= MAX_SEQUENCE:
        raise ValueError("bounded nonempty sequence required")
    if type(retention) not in (int, float) or not math.isfinite(retention) or not 0 <= retention <= 1:
        raise ValueError("retention must be finite and between zero and one")
    if type(angle) not in (int, float) or not math.isfinite(angle) or abs(angle) > 2 * math.pi:
        raise ValueError("finite phase within one full turn required")
    for value in values:
        if type(value) not in (complex, float, int) or not all(math.isfinite(z) for z in (complex(value).real, complex(value).imag)):
            raise ValueError("finite numeric sequence required")


def rotating_state(values, *, retention=0.8, angle=0.5):
    """O(n) host arithmetic, O(1) recurrent state, O(n) returned outputs."""
    _validate(values, retention, angle)
    transition = retention * cmath.exp(1j * angle)
    state = 0j
    outputs = []
    for value in values:
        state = transition * state + (1.0 - retention) * complex(value)
        outputs.append(state)
    return outputs


def rotating_history(values, *, retention=0.8, angle=0.5):
    """O(n^2) direct history for each t; not a trainable attention mechanism."""
    _validate(values, retention, angle)
    transition = retention * cmath.exp(1j * angle)
    outputs = []
    for t in range(len(values)):
        state = sum((1-retention) * transition**(t-j) * complex(value)
                    for j, value in enumerate(values[:t+1]))
        outputs.append(state)
    return outputs


def complex_state_report(values, *, retention=0.8, angle=0.5):
    _validate(values, retention, angle)
    fast = rotating_state(values, retention=retention, angle=angle)
    direct = rotating_history(values, retention=retention, angle=angle)
    limit = max(abs(complex(x)) for x in values)
    residual = max(abs(x-y) for x,y in zip(fast,direct))
    return {
        "schema": "merlin-mamba-inspired-complex-state-reference/1",
        "length": len(values), "retention": retention, "angle_radians": angle,
        "max_input_magnitude": limit, "max_state_magnitude": max(abs(x) for x in fast),
        "max_abs_error_against_direct_history": residual,
        "derivation": "For z_t=a*z_(t-1)+(1-rho)*x_t, z_-1=0 and a=rho*exp(i*theta), induction yields z_t=(1-rho)*sum_(j=0)^t a^(t-j)*x_j.",
        "bound": "For 0<=rho<=1 and |x_t|<=B, |z_t|<=rho*B+(1-rho)*B=B by triangle inequality.",
        "computational_reduction": "Direct history has O(n^2) elementary weighted-sum work; recurrence uses O(n) work and O(1) recurrent state, ignoring output storage.",
        "simulated_carrier": "complex-valued scalar state",
        "physically_realized_device_claim": False,
        "actual_mamba3_model_executed": False,
        "novel_xenomaths_proved": False,
        "general_model_quality_gain_proven": False,
        "production_qualified": False,
    }
