# Choosing the next Merlin experiment

Merlin's reviewer can now pick up to two earlier candidates to use as starting points for a new experiment. The host supplies the completed review. Selection uses each candidate's training-case matches. The separate decision about accepting a change still uses held-out observations and checks for regressions.

## Why this component

GEPA's maintained utility tracks which candidates contribute to the best result on individual examples. Merlin uses its MIT-licensed Python module from v0.1.4. The module imports only the standard library. Its source Git blob is `05567c8b3f69209acebfb1bb460fc4b445006851`. The adjacent license file is the original upstream license. [Pinned upstream source](https://github.com/gepa-ai/gepa/blob/8b0ce6cd99a234f6b74daf37558a2ac0ce18f975/src/gepa/gepa_utils.py)

With three possible parents and a budget of two, Merlin can check every combination. It first maximizes the number of distinct training cases covered, then minimizes the number of slots. GEPA's frontier breaks remaining ties. Identical training results prefer the baseline or, among coders, the first coder. This keeps scheduling deterministic across replay.

Call `plan_training_parents(reviewer, protocol_ref, limit=2)` from `dot_ai_os.training_parents` after a review completes. The result contains exact candidate references, training coverage, and uncovered training IDs. A host can give those references to the next two coders. The function reads existing observations and initiates zero provider calls.

## Measurement

In the existing three-document dot experiment, the two best candidates each covered both training cases. One parent covered the same two cases. In a complementary-case control, selecting by individual scores covered two of three cases. The new planner covered all three with the same two slots. Regression tests exhaust all 512 binary matrices of three candidates and three cases at each budget. These results measure coverage and proposed work. Model quality and saved inference cost require fresh provider runs.

Run `PYTHONPATH=python python scripts/merlin/measure_training_parents.py` from the repository root. [Measurement](../evidence/dot-training-parents-20261117.json)

## Daily research

Start with an observed gap in the current plan. Compare a maintained upstream implementation with the current Merlin behavior. Enumerate a small set of compatible mechanisms, mathematical representations, and falsifying tests. An analogy from another field should name an invariant, a counterexample and a prediction that could distinguish it from the existing explanation.

Keep priors, simulation outcomes, observed measurements and checked proofs distinguishable. An eligible change needs a frozen baseline, evidence on fresh questions, retained regressions and a reproducible cost measure. Dependencies and local inference engines need their own workload measurements. A paper's benchmark can motivate that experiment.
