# Parallax covariance calibration and abstract layouts

This source-only research extension supplies a deterministic synthetic
conditional-token calibration of the Parallax covariance core. It does not
download or train a model, evaluate a trained language model, create a cloud
service, or promote weights. Exact real-arithmetic identities and an abstract
3D layout model are included as separately scoped components.

## Run a bounded calibration

With Python and NumPy already installed, choose a new approved episode identity,
an output directory, a state directory and the exact reviewed source revision:

```bash
timeout 300s python scripts/merlin/parallax_rsi.py \
  --state-dir /absolute/path/state \
  --output-dir /absolute/path/results \
  --run-id approved-episode \
  --source-commit EXACT_REVIEWED_40_CHARACTER_COMMIT
```

The fixed catalogue contains eight arithmetic variants. Selection uses minimum
validation NLL only among variants passing the same maximum output-error gate.
One held-out episode compares the selected method, baseline and reference.
Fixtures, hashes, candidate losses and failures remain in the receipt. All
reported perplexities concern synthetic identity token IDs, not natural text.
The reference teacher generated the labels, so a small sample PPL advantage
below its distribution is not a new quality optimum.

State uses Merlin's existing canonical registry, hash-linked evidence ledger,
loop coordinator and telemetry outbox. Finished episodes return their pinned
receipt without reevaluation. Interrupted numeric operations, changed source,
replacement artifact versions, clock rollback and exhausted budgets require
review. Export and HUD finalization can recover without rerunning the test.
Changing the run ID is not a license for unattended budget renewal.

The 300-second internal wall limit is cooperative; the external `timeout`
provides hard process termination. The explicit array-payload bound covers one
trace, not the whole Python process. Block variants retain full trace inputs
and test merge arithmetic; they are not reduced-memory streaming kernels.
Runtime measurements include reference and metric calculations.

## Render saved evidence and geometry

Matplotlib is additionally required for figures. The calibration renderer reads
an existing receipt and does not reevaluate candidates. Consult its `--help`
for input/output arguments. The layout renderer creates exact JSON, PNG/SVG and
OBJ/OpenSCAD exports:

```bash
python scripts/merlin/render_parallax_layout.py --output-dir /absolute/path/layouts
```

The proposed 32-tile placements use abstract tile pitch, integer-eighth box
bounds and row-major addresses. Fixed compute/KV pairing stays unchanged
between line, plane and stack. KV capacity and byte-hop counts are analytical
quantities; physical timing, energy, thermal behavior and manufacturability are
outside the model. No upstream physical chip specification is asserted.

`formal/MathAI/Parallax/Hardware.lean` contains mathematical statements for
legal addresses, uniqueness, axis-separated half-open boxes, positive weight
mass, centered moments, covariance merge and perplexity ordering. Its exact
assumptions do not establish Python/CUDA correctness, whole-model equivalence
or a verified physical accelerator. Run the project's pinned formal build in
an authorized environment before making project-level qualification claims.

## Focused verification

```bash
python -m unittest discover -s tests -p 'test_merlin_parallax*.py' -v
python -m unittest discover -s tests -p test_merlin_loop_persistence.py -v
```

To advance to real language-model quality work, first pin the actual checkpoint,
tokenizer, licensed corpus, context/stride, masking and resource budget. Retain
compact candidate outputs for independent numerical audits, freeze a fresh
held-out split and preserve no-improvement outcomes. Production promotion is a
separate reviewed action.
