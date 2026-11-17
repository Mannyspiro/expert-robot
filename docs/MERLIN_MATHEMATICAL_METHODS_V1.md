# Shared mathematical method selection for Hermes and Hermes Teacher

Status: conditional method policy and two reference calculations; not a trained scheduler, live model update or independently verified improvement. Both roles should consider these methods across goals when applicable, and explicitly reject them when assumptions or measured benefit are absent.

## Parrondo is a state-dependent mechanism, not a universal recipe

The classic capital-modulo-three construction has A winning with probability 1/2-epsilon. B wins with probability 1/10-epsilon at residue zero and 3/4-epsilon otherwise. A random mixture changes the stationary distribution over states. The combined expected gain therefore need not be the average of the two standalone long-run gains.

With epsilon=1/200 and a 1/2 mixture, the included exact-rational reference gives A=-1/100, B=-73443/8446300, and combined=223/14200 per turn before any mixture overhead. These are deductions within the specified mathematical model, not observed coder gains. Charging sufficient overhead reverses the improvement. Merely mixing state-independent losing choices cannot create the same reversal. If all permitted actions have nonpositive expected increments conditional on every reachable history, the tower property rules out a positive finite-horizon expected sum under integrability; unbounded stopping requires additional assumptions.

The right default is to preserve competent baselines, not deliberately damage individual strategies in order to obtain a paradox label. A useful combination of two already useful methods is complementarity unless the stronger losing/losing/winning criterion is actually established.

Primary method source: Rasmusson and Boman, Analytical Expressions for Parrondo Games (2002), https://arxiv.org/abs/physics/0210094 . The classic probabilities appear in equation (9). History-dependent extensions: Kay and Johnson, Winning combinations of history-dependent games, Physical Review E 67, 056128 (2003), https://doi.org/10.1103/PhysRevE.67.056128 . Limit theorems and relevant long-run assumptions: Ethier and Lee, Limit theorems for Parrondo's paradox, https://arxiv.org/abs/0902.2368 .

## First candidate experiment for Merlin

Use one frozen set of development repair tasks and a separately held-out evaluation. Define a common task-level utility and hard correctness/security constraints before outcomes are inspected. Account for execution time, tokens and total compute, not just number of prompts.

Candidate A emphasizes bounded hypothesis expansion/reframing; B emphasizes constrained implementation and counterexample elimination. These are proposed search operators, not assumed losing strategies. Compare A-only, B-only, preregistered fixed/random switching, a state-aware schedule and the current strong workflow under equal total budgets. Examples of observable state include unresolved constraints, reproducer status, failing-test classes and hypothesis diversity. Any reduced-state Markov assumption must be tested; it is not guaranteed merely by naming those variables.

Randomize independently reset task episodes or use another design that explicitly handles carry-over. Preserve negative outcomes, failed tasks and switching overhead. A beneficial schedule must improve the declared objective without violating per-coder noninferiority and hard safety constraints. Require uncertainty/multiplicity control, untouched heldout assessment and independent review before adoption. A small mean change or two agents agreeing is not sufficient. To claim strict Parrondo, the standalone losses and combined gain must all be supported under the same zero baseline, horizon and accounting.

## Information theory and complementary mathematics

The implementation computes finite-hypothesis expected information gain I(H;Y) in bits from explicit priors and likelihood rows, plus a declared bits-per-cost-unit diagnostic. It checks distribution normalization, finite values, bounds, impossible outcomes and overflow. This is conditional on the supplied probability model; it does not learn or calibrate that model, measure truth, or prove a globally optimal sequence of experiments.

Use this calculation to compare tests that could distinguish competing defect explanations, subject to explicit cost and safety limits. Bayesian experimental design: Foster et al., Variational Bayesian Optimal Experimental Design (2019), https://arxiv.org/abs/1903.05480 .

Further methods are policy options, not newly implemented algorithms: information-directed/contextual exploration, causal interventions and ablations, minimum-description-length/model selection, rate-distortion with explicit semantic loss, sequential-valid uncertainty assessment, Pareto-constrained optimization, stability/control arguments and invariant-preserving reformulations. Fit method to problem and record assumptions; do not inflate a score by deleting important constraints or evidence.

References: Russo and Van Roy, Learning to Optimize via Information-Directed Sampling, https://arxiv.org/abs/1403.5556 ; Howard et al., Time-uniform, nonparametric, nonasymptotic confidence sequences, https://arxiv.org/abs/1810.08240 ; Grunwald, The Minimum Description Length Principle, https://homepages.cwi.nl/~pdg/book/book.html . Sequential inference is needed when outcomes are monitored adaptively; fixed-sample significance tests cannot simply be repeatedly peeked at without adjustment. Compression is not correctness, and information gain is not causality.

## Integration and shared learning

`mathematical_strategy_contract()` supplies a fresh versioned policy to the existing `scientific_loop_contract()`. The prepared teacher handler already binds that contract into its review request. The same policy text is included inside workflow version 2 and its SHA-256, used for newly compiled prompts. Historical prompt bytes are not rewritten. Complete prompt/result compatibility and live entrypoint coverage still require the full exact-source tests.

Hermes proposes experiments and repairs; the teacher audits the mechanism, uncertainty, counterexamples and lesson boundaries. Both receive source-bound lesson proposals; neither automatically modifies model weights, prompts, tests or deployment. Preserve heldout separation, evaluate each coder and the pair, and independently approve versioned adoption/rollback. Runtime observation, formal proof, ordinary tests and authenticated CACE verification remain distinct. An exact toy calculation does not qualify an agent.

Proactive method consideration is intended across tasks, not mandatory use of one formula. Ideonomy can enumerate compatible alternatives at a real blockage; Lacuna-inspired gaps remain hypotheses. A simplex or n-ality representation is admissible only with stated semantics and transfer tests, not as an asserted universal paradox resolution.
