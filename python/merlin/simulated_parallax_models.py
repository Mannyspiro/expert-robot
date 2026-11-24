"""Small, verifiable simulated-state memory experiment.

These scalar recurrences are NOT implementations of Parallax or Mamba-3.
They illustrate an independently provable state-compression identity and
provide a matched-output toy control for proposed model research. All time
measurements are local Python execution, not accelerator training/inference.
"""
from __future__ import annotations

import math
import random
from time import perf_counter


def _valid(values, a):
    if (not isinstance(values, (list, tuple)) or len(values) > 4096
            or type(a) not in (int, float) or not math.isfinite(a) or not 0 <= a <= 1
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in values)):
        raise ValueError("finite bounded signal and damping 0<=a<=1 required")


def quadratic_reference(values, damping=0.8):
    """Direct weighted-history calculation, O(N^2), scalar output at each t."""
    _valid(values, damping)
    result = []
    for t in range(len(values)):
        total = 0.0
        for j in range(t + 1):
            total += (1.0 - damping) * damping ** (t-j) * values[j]
        result.append(total)
    return result


def state_recurrence(values, damping=0.8):
    """Exact algebraic counterpart in real arithmetic, O(N) and O(1) state."""
    _valid(values, damping)
    state = 0.0
    result = []
    for value in values:
        state = damping * state + (1.0-damping) * value
        result.append(state)
    return result


def truncated_local(values, damping=0.8, window=8):
    """Window-limited analogue, O(N*w), deliberately loses older history."""
    _valid(values, damping)
    if type(window) is not int or not 1 <= window <= 512:
        raise ValueError("bounded window required")
    result = []
    for t in range(len(values)):
        start = max(0, t-window+1)
        result.append(sum(
            (1.0-damping)*damping**(t-j)*values[j]
            for j in range(start,t+1)))
    return result


def phase_space_hybrid(values, damping=0.8, window=8, local_mix=0.25):
    """Virtual two-channel carrier: recurrent memory + local-window channel.

    Local mix is a declared interpolation, not an optimal learned gate or a
    physical parallax device. This is a discrete computational representation.
    """
    _valid(values, damping)
    if type(local_mix) not in (int, float) or not math.isfinite(local_mix) or not 0 <= local_mix <= 1:
        raise ValueError("local simplex coordinate must be in [0,1]")
    full = state_recurrence(values, damping)
    local = truncated_local(values, damping, window)
    return [(1-local_mix)*s+local_mix*l for s,l in zip(full,local)]


def run_reference_experiment(n=128, damping=0.8, window=8, seed=23):
    """Return actual CPU timings and accuracy against the same reference.

    Synthetic cases are deterministic given seed. A winning toy timing does
    not establish quality, novelty, FLOP, device, model-weight or energy gains.
    """
    if type(n) is not int or not 1 <= n <= 512 or type(seed) is not int:
        raise ValueError("finite sample length and integer seed required")
    rng = random.Random(seed)
    signal = [rng.uniform(-1,1) for _ in range(n)]
    output = {}
    algorithms = {
        "quadratic_history":lambda:quadratic_reference(signal,damping),
        "scalar_recurrence":lambda:state_recurrence(signal,damping),
        "local_window":lambda:truncated_local(signal,damping,window),
        "simulated_two_channel":lambda:phase_space_hybrid(signal,damping,window),
    }
    for name, fn in algorithms.items():
        t0 = perf_counter()
        predicted = fn()
        seconds = perf_counter()-t0
        output[name] = {"latency_seconds": seconds, "result": predicted}
    target = output["quadratic_history"]["result"]
    return {
        "schema":"merlin-simulated-parallax-memory-benchmark/1",
        "setting":{"n":n,"damping":damping,"local_window":window,"seed":seed,
                   "carrier":"discrete simulated two-channel state"},
        "variants":{
            name:{"elapsed_seconds":item["latency_seconds"],
                  "max_abs_error_vs_reference":max(
                      abs(x-y) for x,y in zip(item["result"],target))}
            for name,item in output.items()
        },
        "formal_claims":[
            "For a in [0,1] and |x_t|<=B, s_0=0, s_t=a*s_(t-1)+(1-a)*x_t remains in [-B,B] by convexity.",
            "Induction gives s_t=(1-a)*sum_(j=0)^t a^(t-j)*x_j in exact arithmetic.",
            "Finite floating point precision and host scheduling can produce differences."
        ],
        "actual_host_runtime_measured":True,
        "synthetic_data_only":True,"formal_proof_assistant_executed":False,
        "trained_model_evaluated":False,"physical_hardware_equivalence_proven":False,
        "production_qualified":False
    }
