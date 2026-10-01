# Artificial interoception

Expert Robot's artificial interoceptive system converts measurable internal
telemetry into bounded metacognitive signals.

It is intentionally separated from personality and emotion-like control:

```
runtime / proof / graph sensors
            |
            v
 artificial interoception
            |
            v
 normalized cognitive signals
            |
            v
 software neuromodulators
            |
            v
 executive search biases
```

This is an engineering control system inspired by the role of interoception in
biological regulation. It is not evidence of subjective experience.

## Sensor inputs

### Resource state

- CPU load
- GPU load
- RAM pressure
- VRAM pressure
- context utilization
- work-queue pressure

### Mathematical/search state

- recent Lean proof success rate
- externally verified progress
- expected verified progress
- theorem novelty
- theorem-graph coverage
- route repetition
- uncertainty
- contradiction rate
- consecutive proof/search failures
- attempts since verified progress
- elapsed time since verified progress
- task-level persistence priority

Language-model self-reported confidence or emotion is not accepted as a sensor.

## Homeostatic model

Resource sensors have configurable operating set-points. Values below a
set-point produce little or no pressure; values above the set-point are
normalized by the remaining headroom.

The aggregate resource-pressure signal is weighted toward context, RAM/VRAM,
and GPU saturation because those limits can materially alter safe search
allocation.

## Stagnation

Stagnation is a bounded combination of:

- consecutive failures,
- attempts since verified progress,
- time since verified progress.

This prevents a single failed Lean tactic from being treated as a cognitive
crisis while still detecting prolonged dead ends.

## Prediction error and surprise

Reward prediction error is:

```
verified_progress - expected_verified_progress
```

and remains signed in `[-1,1]`.

Surprise combines absolute prediction error, deviations from running
progress/proof-success baselines, and contradiction rate.

## Novelty

Novelty combines local theorem novelty with the unexplored portion of the
theorem graph. This encourages broader search without treating novelty as
truth.

## Output state

The persistent interoceptive state contains:

- resource pressure
- cognitive strain
- stagnation
- novelty
- surprise
- uncertainty
- attention demand
- route repetition
- reward prediction error
- verified progress
- goal persistence
- running homeostatic baselines

All unsigned control values are normalized to `[0,1]`.

## Trust boundary

Interoception can influence search allocation only.

It cannot:

- make a theorem true,
- mark a theorem Lean-verified,
- alter the pinned Lean kernel,
- weaken qualification,
- grant filesystem/network/credential authority,
- promote an RSI generation.

Its output feeds software neuromodulators, whose explicit invariants remain:

```
verification_rigor_multiplier = 1.0
authority_delta = 0.0
```

## Intended math use

A prolonged proof dead end can therefore become an objective machine state:

```
failure streak          high
verified progress       low
route repetition        high
uncertainty             high
theorem novelty         available
resource pressure       acceptable
        |
        v
stagnation / surprise / novelty
        |
        v
strategy-switch pressure
        |
        v
breakthrough-mode search
```

The executive may then try lemma decomposition, theorem-graph expansion,
algebra-geometry translation, a different specialist, counterexample search,
or a broader analogy. Every mathematical claim still returns to Lean.
