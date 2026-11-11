# Parrondo's Paradox — zero-first interactive lesson

Status: lesson specification for the Merlin Mathematics & Computational Learning System  
Version: 1.0  
Design rule: concrete experience first; notation only after the learner can explain the observed behavior.

## Learning outcomes

A learner should be able to:
1. Describe a game that tends to lose money and another game that also tends to lose money.
2. Observe that switching between the games in a particular pattern can produce a positive long-run average.
3. Explain why this is not a contradiction: the games change the state-dependent conditions encountered by later turns.
4. Distinguish a mathematical possibility from a guarantee about every finite run.
5. Form a hypothesis, test it with repeated simulations, inspect counterexamples, and explain the mechanism in their own words.

Do not require prior arithmetic fluency. Offer manipulable counters and spoken/visual explanations.

## Lesson flow

### Stage 0 — story, no numbers or symbols

A character plays two coin games. Each game, when played by itself for a long time, tends to leave the character with less money. The character discovers that alternating the games can sometimes make the balance grow.

Ask: “Does that sound impossible, or could the order of the games matter?”

Accept any answer. Do not grade intuition as right or wrong.

### Stage 1 — physical intuition

Render a starting pile of 30 tokens. Each turn animates one token being added or removed. Provide three modes:
- Game A only
- Game B only
- Alternate A and B

Use a reproducible seed and show the seed. Let the learner replay with another seed. Keep the same number of turns when comparing modes. Explain that a short run can go either way.

### Stage 2 — reveal the rules with visual state

Introduce a three-position track representing the current token count's remainder when grouped in threes. Do not call it a modulus yet. Highlight the current position.

Rules for the canonical teaching example:
- Game A: each turn has an equal chance of gaining one token or losing one token. Its expected change is zero.
- Game B: when the balance is divisible into groups of three with nothing left over, the chance of gaining one token is 1/10; otherwise the chance is 3/4. A loss happens on the complementary outcome.

Important precision: this canonical Game A is fair, not losing. Game B is losing in the standard parameterization. The paradoxical result is that a suitable mixture can outperform either game. A second, optional parameterized variant may make both games strictly losing; label it as a variant and numerically verify its parameters before presenting it.

### Stage 3 — experiment before equations

Offer side-by-side repeated trials for A-only, B-only, and alternating A/B. Use the same starting balance and trial length. Show:
- balance over time,
- distribution of ending balances over many independent runs,
- fraction of runs that end above the starting balance,
- average ending balance and uncertainty interval,
- exact rule set, seed, and number of trials.

Never imply every alternating run wins. Explain sampling variation and distinguish average outcome from an individual trajectory.

Default simulation controls: 30 starting tokens, 3,000 turns, 1,000 trials. Let learners reduce the trial count for speed or increase it to see the average stabilize. Clearly label these as teaching defaults, not theorem assumptions.

### Stage 4 — learner predicts, then tests

Prompt before revealing results:
- “Which game do you predict will do best alone?”
- “What do you predict will happen when we alternate?”
- “What changed when the balance moved between the three positions?”

Capture the prediction, confidence, explanation, selected strategy, simulation seed, and observed result as separate evidence fields. A wrong prediction is useful evidence, not a penalty.

### Stage 5 — introduce names and notation

Only after the learner can describe the mechanism:
- “remainder” / “position in the three-step cycle”
- “probability” as a long-run frequency model
- “expected change” as the average change over many repetitions
- modular arithmetic notation for the three positions
- Markov chain as a compact description of state transitions

Reveal equations progressively, with a plain-language translation beside each one. Never gate the intuitive lesson on reading algebra.

### Stage 6 — deeper mathematical explanation

Explain that Game B's favorable and unfavorable probabilities depend on the current state. Game A moves the balance between states; alternating changes how often Game B is encountered in each state. The combined process therefore has a different stationary distribution from either isolated process. The gains and losses are weighted by the state frequencies, so the combined expected behavior can be positive.

For the formal track, derive the transition matrix over the three remainder states, compute its stationary distribution, and calculate the expected gain per turn. Show all assumptions and use a numerical check. For the mathematician track, ask the learner to derive and justify the stationary distribution. For the mathematics-programmer track, implement the simulator and validate it against the analytic result. For the computational-hacker track, investigate seeds, state encodings, random-number generators, and statistical error.

## Interactive renderer contract

The renderer should consume a typed lesson document, not hard-code this lesson into UI components.

Required block types:
- `story`: narration, image/video references, optional audio.
- `manipulative`: stateful visual tokens/objects and permitted actions.
- `choice`: prediction or strategy selection, with no shame language.
- `simulation`: deterministic seed, parameters, repetitions, and reproducible output metadata.
- `chart`: time series and outcome distributions with accessible textual descriptions.
- `explanation`: progressive disclosure, glossary, and optional notation.
- `reflection`: learner's own explanation and confidence.
- `retrieval`: spaced-repetition prompt linked to prior concept IDs.
- `assessment`: rubric dimensions and evidence provenance.

Every interaction emits an event with learner ID, lesson/version, stage/task ID, event type, timestamp, response or action, hint count, seed/parameters when relevant, and evidence references. Do not store raw sensitive voice/video by default; store derived learning signals and explicit consent metadata.

The renderer must:
- preserve stage order and enforce the concrete-before-symbolic invariant;
- support keyboard, touch, screen-reader labels, reduced motion, captions, and text alternatives;
- pause/resume without losing progress;
- allow replay and alternate seeds;
- distinguish generated illustration from measured simulation output;
- show uncertainty and avoid overstating conclusions;
- never award mastery solely for watching or clicking through.

## Mastery and evidence

Score independently across conceptual understanding, procedural execution, representation, transfer, proof/reasoning, and retention. A single multiple-choice answer is insufficient for mastery. Require at least two evidence types over time, such as explanation plus a successful prediction, or implementation plus a validated result.

Hints reduce the independence weight but never erase learning. A learner can retry without penalty. Store the attempt event first; update mastery only from validated, attributable evidence. Keep lesson completion separate from mastery.

## Spaced repetition plan

Create retrieval prompts for:
- immediately after the lesson,
- the next day,
- 3 days,
- 7 days,
- 14 days,
- 30 days.

These are initial scheduling defaults. Adapt using recall quality, response latency only when appropriate and consented, confidence calibration, hint use, and later transfer. Failed recall should shorten the next interval and trigger a different representation; successful independent recall should lengthen it. Do not use speed as the primary measure.

Prompts should progressively vary:
1. Explain the paradox without symbols.
2. Predict what happens when the order of games changes.
3. Identify the state that controls Game B's rule.
4. Explain why a short losing run does not refute a positive long-run expectation.
5. Transfer the idea to another state-dependent system.

## Validation and acceptance criteria

- A first-time learner can complete the first three stages without reading letters, equations, or probability notation.
- The simulator is deterministic for a fixed seed and parameters.
- A-only and B-only outcomes, and the combined strategy, are reported with trial counts and uncertainty; no claim is made from a single path.
- The analytic transition model agrees with simulation within a documented statistical tolerance.
- The lesson explicitly says that the canonical Game A is fair, while Game B is losing.
- Every learner interaction produces a typed attempt event; events persist and can be replayed/audited.
- Spaced repetition schedules retrieval rather than merely repeating the original video.
- The three learning paths share the same canonical concept and evidence records; they vary activities, not duplicated learner databases.
- No mastery is awarded from exposure alone.
- CI tests cover lesson schema validation, stage-order invariants, deterministic simulation, statistical sanity bounds, event persistence, and scheduler behavior.

## Next engineering steps

1. Implement the typed lesson-document schema and validator.
2. Implement a renderer adapter for story, manipulative, choice, simulation, chart, reflection, and retrieval blocks.
3. Implement the Parrondo simulator as a pure deterministic function with explicit RNG seed and configuration.
4. Add analytic transition-matrix calculation and simulation-vs-analysis tests.
5. Connect all events to the existing learner evidence store and canonical concept registry; do not create parallel registries.
6. Add retrieval scheduling to the existing learner-state model and test interval adaptation.
7. Run the full CI suite and report actual checks. A commit or empty status list is not evidence of passing CI.
