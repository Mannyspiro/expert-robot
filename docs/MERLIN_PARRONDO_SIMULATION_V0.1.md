# Parrondo simulation and learner-session integration

The Parrondo discovery activity is now represented as a native Merlin `LessonSpec`, so the existing sequential `LessonSession` runtime can advance it without a parallel lesson-state implementation. Its target concepts are registered in the prerequisite graph: state, probability, expected value, state transitions and Markov chains, building from quantity. The first five stages are concrete play, observation and visual explanation; symbols appear only at the final stage.

`python/merlin/parrondo_simulation.py` adds reproducible finite-run experiments:
- a seeded game trajectory with every visited integer total;
- equal-turn A/B/mixture comparisons;
- independent repeated trials with sample standard deviation, standard error and a descriptive normal-approximation 95% interval.

The simulation does not establish the long-run theorem. The stationary expectation is computed separately from finite simulation using a closed-form Markov chain tree calculation in `parrondo_lesson.py`. A finite trajectory may lose even when the stationary expected gain is positive. The approximate interval is descriptive and should not be treated as an exact finite-sample guarantee.

Run the focused tests with:

```sh
PYTHONPATH=python python3 -m unittest discover -s tests -p 'test_merlin_parrondo*.py' -v
```

The current CI workflow includes the focused deterministic tests. Production qualification still requires a successful runner execution and review of the complete repository test suite.
