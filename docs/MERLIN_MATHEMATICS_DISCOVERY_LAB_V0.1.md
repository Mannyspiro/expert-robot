# Merlin mathematics discovery lab — browser vertical slice v0.1

## Purpose

The HUD now includes a Mathematics Lab view for a zero-first introduction to Parrondo's paradox. It is a local browser experiment: it requires no model endpoint, external JavaScript package, API key, account, or additional service.

## Learner flow

1. Choose Game A, Game B, or the random A/B mixture.
2. Play 1, 25, or 250 turns and observe the running total, wins, losses, and trajectory.
3. Compare the three games by resetting each game to the same pseudo-random seed.
4. The mathematical explanation remains hidden until at least 25 turns have been played.
5. Reveal the state-based model and the stationary expected gains.

## Model

A win changes the running total by +1; a loss changes it by -1. Game B uses a different win probability for each residue class modulo three. The mixture chooses A or B with equal probability on each turn.

For epsilon = 0.005:
- A: p = 0.495 in each state; stationary expected gain = -0.010000.
- B: p = (0.095, 0.745, 0.745); stationary expected gain is approximately -0.008695.
- Mixture: p = (0.295, 0.620, 0.620); stationary expected gain is approximately +0.015704.

The UI's displayed expected values are calculated from the stationary distribution. They are long-run expectations, not finite-run guarantees. The simulation is an illustration, not a proof; the Python lesson module and its Markov-chain tests are the separate mathematical calculation.

## Implementation boundaries

- Uses browser-native JavaScript, SVG and CSS only.
- Does not make network requests from the experiment.
- The pseudo-random generator is seeded for reproducible resets.
- The experiment is in-memory and does not persist learner identity or progress.
- No mastery credit, assessment result, or CACE receipt is created by playing.
- No external inference provider or model is required.

## Next steps

1. Add accessible keyboard and screen-reader narration for state changes and plot summaries.
2. Add a learner response prompt and record attempts through the existing learning store only when a learner identity and persistence boundary are deliberately designed.
3. Connect the experiment to the concept registry and the three learning paths.
4. Add independent numerical cross-checks between browser expected values and the Python calculation.
5. Add browser automation when a free, already available runner/browser is verified; do not introduce a paid service or require user configuration.
