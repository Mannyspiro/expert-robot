# Software neuromodulators

Expert Robot uses four bounded software neuromodulator analogues as a
metacognitive control layer.

They are engineering abstractions inspired by computational roles associated
with neuromodulatory systems in neuroscience. They are not biological
simulations, evidence of subjective emotion, or claims that the system feels.

## Channels

All channels are deterministic and normalized to `[0,1]`.

- **dopamine-like** — verified progress and positive reward-prediction signal
- **norepinephrine-like** — surprise, uncertainty, stagnation, route repetition
- **acetylcholine-like** — attention demand and expected uncertainty
- **serotonin-like** — persistence/inhibition under resource constraints

## Inputs

The controller consumes signals produced by artificial interoception:

- verified progress
- reward prediction error
- surprise
- uncertainty
- novelty
- attention demand
- stagnation
- route repetition
- resource pressure
- goal persistence

LLM self-reported emotion or confidence is not a trusted input.

## Executive outputs

The state produces bounded biases:

- exploration drive
- persistence drive
- attention allocation
- strategy-switch pressure
- compute conservation
- breakthrough-mode trigger

These may change which search strategy receives compute, but cannot change the
standard for mathematical truth.

## Hard invariants

Every update returns:

```
verification_rigor_multiplier = 1.0
authority_delta = 0.0
```

Neuromodulation therefore cannot lower Lean qualification requirements or
grant new filesystem, network, credential, or promotion authority.

## Breakthrough mode

Breakthrough mode is enabled only when both stagnation and strategy-switch
pressure cross configured thresholds.

The executive can use this to try broader theorem-graph search, lemma
decomposition, algebra-geometry translation, counterexample search, or another
specialist. All candidate results still require ordinary verification.
