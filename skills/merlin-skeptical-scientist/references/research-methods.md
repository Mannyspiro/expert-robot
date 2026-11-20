# Method selection and grounding

| Question | Useful method | Limit |
| --- | --- | --- |
| Contract satisfied? | Minimal reproduction, invariants, negatives, regression/fault injection | Covers tested behavior, not all inputs |
| Intended outcome improved? | Frozen baseline, paired workloads, held-out quality/cost and uncertainty | Synthetic fixture does not establish general gain |
| Mechanism identified? | Alternatives, controls/ablations, falsifiers, sensitivity | Prediction agreement need not uniquely identify cause |
| Computation reproducible? | Exact data/code/environment and replay | Repeat computation is not new-data replication |
| Model relevant to reality? | Units/boundaries, calibration, external measurements/mismatch | Internal consistency is not physical validity |
| Analogy simplifies problem? | Invariant mapping, small subproblem, translation-back test | Transfers only justified structure |
| Useful combinations missing? | Constrained finite enumeration and coverage accounting | Gaps are catalogue/ledger-relative |

Keep exploration productive. A prior plan distinguishes planned tests from post-hoc exploration; it does not guarantee correctness or unbiased interpretation. Report deviations, planned outcomes and null results.

Grounding sources reviewed November17,2026:
- [National Academies definitions](https://www.nationalacademies.org/read/25303/chapter/3): computational reproducibility, replication and generalization.
- [National Academies scientific methods](https://www.nationalacademies.org/read/25303/chapter/5): discovery, confirmation and correction.
- [Center for Open Science preregistration](https://www.cos.io/initiatives/prereg): exploratory/confirmatory distinction and reporting planned outcomes.
- [NIST SP800-142](https://csrc.nist.gov/pubs/sp/800/142/final), [IR7878](https://csrc.nist.gov/pubs/ir/7878/final): specified interaction coverage.
- [Stanford Encyclopedia of Philosophy, Analogy](https://plato.stanford.edu/archives/fall2024/entries/reasoning-analogy/): structural mappings and relevant disanalogies.

The bias/fallacy map is an operational aid, not a validated diagnostic or a guarantee that an assistant can detect/eliminate every bias. Prefer external checks over introspection alone.
