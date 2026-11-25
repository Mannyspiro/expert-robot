# Bounded offline Parallax language-model pilot

This pilot evaluates the pinned `YifeiZuo/Parallax-0.6B` checkpoint at revision
`0cf73e2d49ea1a09a9ef85178b73ad68e019ae36` on two fixed natural-text windows.
It provides a small numerical diagnostic. It does not establish representative
language-model quality, a minimum achievable perplexity, or a hardware speedup.

## Comparison

The baseline is the unmodified attention kernel shipped with the checkpoint.
The single candidate is centered covariance **with explicit softmax-mass
normalization**. For `m=sum(p)`, `A=sum(p*a)`, `S=sum(p*v)`, and `T=sum(p*a*v)`,
the real expressions are:

```text
checkpoint baseline: S + A*S - T
normalized candidate: (S-T)/m + A*S/(m*m)
```

They coincide when the mathematical mass is one. Rounded softmax entries and
reduction order introduce differences. A floating-point change cannot be
attributed solely to centering without another separately frozen ablation.
The exact real-algebra Lean theorems do not certify this Python program or its
floating-point errors.

The candidate supports CPU FP32, batch one, at most 129 query/key positions,
16 query heads, and head dimension 128. It requires inference mode, disabled
CPU autocast, evaluation mode, and zero dropout. It preserves GQA ordering,
QK scaling, unscaled RK, supplied mask precedence, causal prefix offsets, and
the output layout. It deliberately accepts a narrower additive-mask domain
than the checkpoint kernel; unsupported shapes and nonfinite results fail.

## Frozen evaluation

1. Recover and verify the existing ten-file checkpoint, standalone Python,
   and dependency wheels from recorded locks. The runner never downloads or
   installs them. Review both custom checkpoint Python files before execution.
2. Provide `validation.txt`, `test.txt`, and `corpus-manifest.json`. The manifest
   contains `sources` entries with `split`, `path`, and `sha256`, plus source
   and licensing context. Choose distinct texts before observing scores.
3. `prepare` verifies all checkpoint files, tokenizes locally without a chat
   template, padding, or inserted special tokens, and freezes the first 129
   IDs per split. It records runtime, source, tokenizer, and input identities.
   It performs no model forward pass.
4. Commit the final source and prepared protocol. Execute under the required
   external hard timeout. Two CPU threads and one interop thread are fixed.
   Parameters are loaded as FP32; no cache, gradients, dropout, or weight
   updates are used.
5. Score the author baseline and one candidate on validation. Require finite
   full-vocabulary logits and maximum absolute logit difference at most
   `1e-3`. Select lower validation mean NLL among eligible candidates, with
   baseline winning an exact tie.
6. Run one test episode after selection: baseline and the selected candidate,
   with the baseline result reused when it was selected. Do not alter the
   candidate, gate, text, or selection rule in response to the test result.

Each split supplies 128 input tokens and 128 shifted next-token targets:
`inputs=ids[:-1]`, `targets=ids[1:]`. Loss uses FP64 shifted log-sum-exp and the
same shifted target logit, in 16-position chunks. Perplexity is the exponential
of mean token NLL. A single contiguous window does not provide 128 independent
observations; no IID confidence interval is produced. Public literary text may
have appeared in pretraining; held out refers only to this candidate selection.

## Invocation

Use the verified runtime and replace the uppercase arguments with explicit
paths. Do not reuse a protocol after changing its source or environment.

```bash
VERIFIED_PYTHON -B scripts/merlin/parallax_lm_rsi.py prepare \
  --checkpoint-dir CHECKPOINT_DIR --checkpoint-lock CHECKPOINT_LOCK \
  --corpus-dir CORPUS_DIR --protocol FROZEN_PROTOCOL

timeout --signal=KILL 300s VERIFIED_PYTHON -B \
  scripts/merlin/parallax_lm_rsi.py execute \
  --checkpoint-dir CHECKPOINT_DIR --checkpoint-lock CHECKPOINT_LOCK \
  --protocol FROZEN_PROTOCOL --state-dir STATE_DIR --output-dir OUTPUT_DIR \
  --run-id UNIQUE_RUN_ID --source-commit EXACT_SOURCE_COMMIT
```

The internal 300-second budget covers model load, validation, selection, test,
and intermediate persistence. The external timeout also bounds dependency
imports and finalization and can terminate an unresponsive native forward.
Cooperative Python deadline checks alone cannot enforce that hard boundary.

## Evidence, recovery, and display

The runner uses the existing research registry, loop coordinator, hash-linked
evidence ledger, and event outbox. Every operation has one attempt. A completed
episode returns verified stored evidence without loading the model. An
incomplete or interrupted episode refuses replay and time-budget renewal.
Partial initialization, changed source, superseded artifact versions, altered
receipts, and changed retained outputs fail closed.

There is one narrow reviewed recovery path for a failure during model-load
metadata recording, before any scoring operation starts. It requires a new
run identity, the exact parent ledger and initialization anchors, unchanged
experimental semantics and candidate, and a single consumed recovery claim.
The original absolute deadline remains in force internally and in a shorter
external timeout. Any validation or test attempt makes this path ineligible.
It is not an automatic resume, a new budget, or permission to replay a scored
or ambiguous forward.

Full FP32 logits and all token losses are retained for independent audit.
There are at most four logit arrays, each bounded to 128 MiB; the actual pinned
shape is 128 by 151936. These output artifacts have a separate budget from the
earlier small attention-input fixture. Their presence does not demonstrate
reduced-memory paging. The registry and exported files can contain duplicate
copies; account for that storage when checkpointing the episode.

Each forward records the 28 installed attention-kernel invocations and their
layer indices, input shapes, dtypes, and mask hashes. The original dispatch is
restored in a `finally` block. Baseline and candidate traces must agree.

`render_parallax_lm.py` renders saved receipts and their adjacent protocol;
it does not load a checkpoint or perform inference. Register its exact PNG/SVG
and provenance in the research view. A saved figure is historical evidence,
not proof that a live OCI service or browser stream is running.

## Tests and boundaries

`test_merlin_parallax_torch.py` uses tiny synthetic tensors and an independent
FP64 raw-moment oracle. `test_merlin_parallax_lm.py` exercises numerical loss
stability, alignment, frozen protocol validation, and persistence boundaries.
Missing Torch causes explicit candidate-test skips; skips do not satisfy the
runtime gate.

This work makes no production promotion, paid allocation, model download, or
OCI deployment. It does not implement a calibrated chip simulator, a physical
layout sign-off, thermal/electrical verification, or a proof of compiled CUDA.

Primary project references:

- <https://huggingface.co/YifeiZuo/Parallax-0.6B>
- <https://github.com/Yifei-Zuo/Parallax>
- <https://arxiv.org/abs/2605.29157>
