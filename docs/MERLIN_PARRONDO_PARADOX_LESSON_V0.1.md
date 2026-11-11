# Parrondo's paradox: zero-first learning experiment

## Learning sequence

The lesson starts with a concrete question, not algebra: can two games that each tend to lose money become beneficial when mixed? Learners play each game, observe the state-dependent rule, compare the mixture, and only then see probabilities and expected values.

## The canonical three-state example

Each turn changes a running total by +1 on a win and -1 on a loss. Game A uses the same coin every turn. Game B chooses a coin based on the current total modulo three: a comparatively poor coin at state 0, and a better coin at states 1 and 2. The mixture independently chooses A or B with equal probability on every turn.

For epsilon = 0.005:
- Game A win probability: 0.495; expected gain per turn: -0.010000.
- Game B win probabilities by modulo state: 0.095, 0.745, 0.745; stationary expected gain per turn: approximately -0.008695.
- Random A/B mixture: expected gain per turn: approximately +0.015704.

These are long-run stationary expected gains for this parameterization, not guarantees about every finite run. A short play session can still lose. The mechanism is state occupancy: the mixture changes how often the process visits each modulo state.

## Implementation boundaries

The Python module computes the modulo-3 stationary distribution by iterating the finite Markov chain and calculates stationary expected gain. It does not claim that simulation proves the result. Tests check the sign and expected values for the stated parameterization.

The strategy-portfolio experiment in the learning core is a separate educational-policy hypothesis. It must not be conflated with the mathematical paradox: evidence that a mixed teaching strategy helps learners requires randomized studies, delayed outcomes, uncertainty intervals, and replication.
