# Locked G4–G10 experiment

Continue the qualified G3 source `0b4c9b29e50890785fbe36d4a849e297f480bcd1`
through the previously locked G4–G10 roadmap at
`9d4968631a7cac64c096c08629c4016656743b77`. All seven candidate commits were
created before receiving evaluation cases or results. `candidates.json` records
their exact source commits, parents, configuration hashes and staging branches.
The candidates change only `config/proof_search.json`.

`Locked RSI Through Gen10` runs one Avrea 8-vCPU worker, with a 45-minute job
limit, read-only repository permissions, pinned Lean 4.34.0 and two independent
repetitions. The job verifies independently written mathematical witnesses,
builds C++ with assertions enabled, runs the runtime checks, then evaluates G3
and every G4–G10 candidate. It uploads partial evidence on failure.

The validation suite has 12 scored cases; the final holdout has 10. Two trivial
schema fillers in each suite satisfy the existing executable's three-split
requirement and are excluded from scoring. The final suite is first interpreted
by the sweep after validation selection is locked. The witness verification
step may inspect it beforehand but does not generate or edit candidates.
Suite files are now published for reproduction and must not be reused as fresh
hidden data in later experiments.

Ranking prefers consistently Lean-verified cases, then fewer proof attempts,
with no regression on a champion's consistently solved cases. A tie retains the
champion. The candidate lineage remains G3→G4→…→G10 even when candidates are
rejected. The original runtime configuration is restored after every candidate
and after failures or interruption.

This is an external assistant's evaluation of a locked roadmap. It uses real
Lean proof search with zero model calls. It does not claim autonomous proposals,
modified model weights, official collared qualification, or promotion. The
paired repetition count meets the experiment policy minimum; no optimal-budget
claim is made. The runtime's 20-second limit applies to each tactic subprocess,
not to a whole case. The sweep bounds each benchmark invocation to 900 seconds.

Project-chat feedback preserved in a repository checkpoint and identifiable
review findings are recorded in `feedback.json`. Other ChatGPT project chats
were not directly retrieved. Exact-source, CACE evidence-parent and blind-view
repairs are a separate trusted-infrastructure change.

To replay after building the pinned Lean package and C++ runtime:

```bash
python3 scripts/run_locked_rsi_sweep.py \
  --repo . --executable build/expert_robot_math_benchmark \
  --roadmap experiments/locked-g4-g10-20261002/roadmap.json \
  --baseline-config experiments/locked-g4-g10-20261002/g3-proof-search.json \
  --candidate-manifest experiments/locked-g4-g10-20261002/candidates.json \
  --validation-suite experiments/locked-g4-g10-20261002/validation_suite.json \
  --holdout-suite experiments/locked-g4-g10-20261002/final_suite.json \
  --output-dir build/locked-rsi-gen10-replay \
  --repetitions 2 --timeout-seconds 900
```

Use a new output directory for each replay. The runner refuses to overwrite
evidence and validates source objects, dependency revisions, executable hashes,
suite hashes and distinct candidate configurations.
