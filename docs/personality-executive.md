# Personality executive

Expert Robot's personality module is a stable executive temperament that
combines **logic** with transient **interoceptive/neuromodulatory state**.

It does not make the system a person and does not establish subjective
experience. Its purpose is to provide a stable, testable search policy for
mathematical research.

## Control hierarchy

```
objective runtime / proof telemetry
              |
              v
      artificial interoception
              |
              v
     software neuromodulators
              |
              +-------------------+
              |                   |
              v                   v
       transient biases     logical assessment
              |                   |
              +---------+---------+
                        |
                        v
              personality executive
                        |
                        v
               cognitive action
                        |
                        v
          math / code / research agent
                        |
                        v
                       Lean
```

Personality therefore **interprets** transient emotion-like signals rather than
being replaced by them.

## Math-researcher profile

The initial profile is intentionally both imaginative and skeptical:

| Trait | Value | Intended effect |
|---|---:|---|
| openness | 0.90 | permits distant representations and analogies |
| conscientiousness | 0.98 | favors systematic work and checking |
| persistence | 0.90 | tolerates difficult proof routes |
| skepticism | 0.98 | strongly values counterexamples and verification |
| novelty seeking | 0.80 | explores new theorem/search territory |
| risk tolerance | 0.55 | allows speculation without dominating the search |
| abstraction bias | 0.70 | looks for higher-level structure |
| compression drive | 0.85 | seeks simpler/general statements |

The profile is stable inside a `PersonalityExecutive`. It does not silently
rewrite its own personality during a reasoning episode.

## Logical assessment

The executive receives objective route-level metrics:

- evidence strength
- expected success
- expected information gain
- contradiction risk
- decomposition value
- counterexample value
- abstraction value
- compression value
- representation-switch value
- current-route progress
- branch cost

These values should ultimately come from proof/search/benchmark machinery, not
from an LLM announcing its own confidence.

## Cognitive actions

The first executive can choose among:

1. continue current route
2. explore a novel route
3. decompose the problem
4. seek a counterexample
5. abstract/generalize
6. compress/simplify
7. switch representation
8. intensify verification
9. conserve compute

Every action receives a deterministic score computed from personality, logic,
interoception, and neuromodulation.

## Example: productive route

High expected success + verified progress + low stagnation:

```
persistence
+ conscientiousness
+ logical progress
+ persistence-drive
        |
        v
CONTINUE CURRENT ROUTE
```

## Example: contradiction

High contradiction risk + uncertainty + a skeptical personality:

```
skepticism
+ counterexample value
+ contradiction risk
+ surprise
        |
        v
SEEK COUNTEREXAMPLE
```

## Example: mathematical dead end

High stagnation + repeated route + a promising alternate representation:

```
openness
+ novelty seeking
+ strategy-switch pressure
+ representation-switch value
        |
        v
SWITCH REPRESENTATION
```

For Expert Robot this can later mean:

- algebra -> geometry
- geometry -> algebra
- analytic -> combinatorial
- direct proof -> contradiction
- theorem proving -> counterexample search
- local tactic search -> recursive lemma decomposition

## Breakthrough mode

When neuromodulation marks a true stagnation state as breakthrough mode, the
personality executive boosts exploratory escape routes according to its stable
traits.

A highly open profile boosts exploration and representation switching.
A highly persistent profile boosts decomposition.
A highly skeptical profile boosts counterexample search.
A high abstraction bias boosts generalization.

This is deliberately more structured than simply raising LLM temperature.

## Trust invariants

Personality can change search order and compute allocation only.

It cannot change:

```
verification_rigor_multiplier = 1.0
authority_delta = 0.0
```

It cannot mark a theorem as proved, weaken Lean, expand permissions, or promote
an RSI generation.

## Scientific evaluation

Personality should be treated as a hypothesis, not assumed to be beneficial.
Benchmark variants should compare:

- no personality layer
- fixed personality
- alternate fixed profiles
- personality + neuromodulation
- personality + neuromodulation + interoception

The primary metric remains **Lean-verified mathematical progress per unit of
compute**, with novelty, route diversity, dead-end escape time, and useful
lemma production as secondary measures.
