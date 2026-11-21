# Weight-bound coder contract implementation note

## Initial frame

Question: can one existing coder stage bind a host-declared weight candidate to
invocation-specific host evidence while retaining canonical replay and the
existing no-automatic-retry rule?

Scope: isolated code candidate copied from the 117-file process-recovery source
map `76b9e39f143c4eac83e360b30c53e9c64cdd0df761e711c493766d70c2f66926`.
The native acceptance source in `merlin-build` and `oci-validation` stays frozen.

Observed premise: `DualCoderWorkflow` already stores immutable provider/input
intents before callbacks and fences an intent without a result. Its provider
identity is a declaration, not loaded-weight evidence. Its v1 payload and result
schemas do not carry a weight receipt.

Hypothesis: an opt-in `coder_a` manifest plus authenticated invocation receipt,
linked from an explicitly versioned stage result, closes that binding gap without
new execution capability. A hash establishes identity; the separately supplied
host authenticator establishes only the configured host's admission of evidence.

Falsifiers: accepted identity mismatch; result accepted without exact receipt;
cross-session receipt reuse; callback mutation changing persisted intended data;
automatic callback repetition after interruption; fresh status falsely reporting
completion; or rewriting existing v1 records.

## Chosen boundary

- Use only MerlinRegistry/ArtifactRef and the existing workflow lock and intent.
- Opt in through a separately constructed host binding for coder A.
- Distinguish intended model/runtime/provider identity from an observed completed
  invocation. Bind session, source, intent, request, inputs and output.
- Keep the original integration adapter digest separate from weight and
  transformation identities.
- Store the normalized candidate with its observed receipt before publishing the
  stage result. An orphan receipt stays pending; no inferred provider retry.
- Validate bound records during normal execution, replay and fresh status reads.
- Keep unbound v1 behavior and historical bytes intact.
- No model loading, weight editing, model calls, downloads, paid operations,
  runtime grants, merge/deploy, model-quality or independent-verification claim.

## Bounded verification plan

Exercise the actual canonical workflow with synthetic callbacks: exact binding;
each identity mismatch; tampered bytes and references; other-session evidence;
literal-True authentication; detached mutable inputs; interruption before and
after durable receipt; fresh-host replay/status; and v1 compatibility. Count
callback invocations so a superficially correct status cannot hide a repeat.

Run the focused tests first. Run the existing source shard once after the new
slice is stable, or leave that combined gate to the root reviewer. Preserve failed
test observations and fixes below; never label fixture evidence as model execution.

## Representation and bias checks

- Simplex: not applicable; no convex weight mixing is implemented.
- n-ality: applied by keeping provider, adapter, runtime, checkpoint, tokenizer,
  configuration, transformation, input, output and authority identities distinct.
- Continuum: deferred; no numerical model behavior is measured.
- Fuzzy logic: not applicable to these exact Boolean identity/authentication gates.
- Avoid evaluator leakage and benchmark optimism: this patch measures software
  binding behavior only, with no model-quality outcome or production-benefit claim.

## Observations and review

Implemented in `python/merlin/weight_binding.py`, with opt-in integration in
`python/dot_ai_os/dual_coder.py` and actual-workflow tests in
`tests/test_weight_binding.py`. The opt-in constructor argument is
`coder_a_binding=WeightBinding(registry, project_id=..., manifest_ref=...,
authenticate=...)`. The binding and workflow must use the same registry instance.

Bound spec, coder A intent/result, final research report and status output use
version 2. Coder B and evaluator result records remain version 1. Historical
unbound version 1 records can still be inspected, but cannot be silently upgraded
or reexecuted as bound under the same session ID.

The bound callback returns exactly `payload` and `observation`. A completed
observation binds the full callback request digest, original input digest, output
digest, source/session/stage/intent, manifest, provider, integration adapter,
runtime, loaded model/shards/tokenizer/configuration and runtime/load session.
The manifest separately preserves transformation, rollback and protocol identity.
The authenticator sees a detached complete receipt and canonical digest. Its
literal `True` admits evidence only under that configured host trust boundary.

The receipt stores the normalized candidate as well as the observation. It is
written before the stage result, which points to its exact ArtifactRef. A receipt
without a result remains `reconciliation_required`; a crash after the result
commit permits only the remaining stages to continue. Fresh status/run re-read
and re-authenticate the receipt. Missing, altered or revoked evidence fails closed.
Canonical manifest, context, intent, rollback and protocol bytes are rechecked;
callback/authenticator mutations of detached inputs cannot rewrite stored data.

Metadata ceilings are 64 KiB for manifests and observations, 256 KiB for a receipt,
and 2 MiB for the complete bound callback request. The existing 512 KiB context
and 64 KiB candidate ceilings remain. Shard count is 1–128, names are bounded
identities, sizes are strict positive integers and not Boolean values. No shard
path is opened and no tensor is parsed.

Focused run 1: 38 tests, 37 passes and one fixture error. The fixture attempted to
delete an artifact version, and the real canonical registry correctly rejected it
with its append-only trigger. No production invariant failed. The corrected
fixture appends an incomplete stage publication pointing at a nonexistent receipt
and verifies that status and run reject it. The original log is retained as
`/workspace/scratch/5023195e1251/wsp-binding-verification/focused-01.log`.

Focused run 2: 39 tests passed in 2.582 seconds, including an additional
noncanonical/duplicate-JSON manifest case. Full test IDs and results are retained
in `/workspace/scratch/5023195e1251/wsp-binding-verification/focused-02.log`.
This is synthetic software-contract evidence. No weights were loaded or edited,
no model endpoint was contacted, and no model-quality improvement or independent
verification was observed. The current native acceptance source is unchanged.

Combined local run: 425 tests passed in 28.080 seconds, with no failures, errors or
skips. The 386 pre-existing tests and 39 new contract tests all executed. The
119-file source map was unchanged during the run:
`31e09554a56f5098531e758b43903f86890bdac57896039a61e3c655a4125a52`.
The executed software inventory digest is
`5f77a8fc3e1c44a553213a00b04699baf1175255c90d170d506221eb1ddc13d8`.
`/workspace/scratch/5023195e1251/wsp-binding-verification/combined-01.log` and
`combined-result.json` retain the full log, planned/executed IDs, source hashes,
counts and scope flags. This run included the frozen code's final docstring.

At this initial checkpoint, independent review and source-specific native
acceptance were pending; the repair and final local-validation sections below
record the subsequent work. The earlier 386/8/6 native gate belongs to its own exact
process-recovery source, not to this new WSP contract candidate.

## Independent review repair

The independent reviewer found two defects in the initial 425-test candidate.
Both were reproduced before modification and are retained in
`/workspace/scratch/5023195e1251/wsp-binding-verification/negative-controls-before-fix.json`:

1. A host that revoked authentication during coder B could still reach evaluator
   execution and report publication. Fresh status then rejected the same evidence.
2. A receipt without an invocation intent was rejected by status, but the run path
   still created an intent and called coder A before encountering the receipt conflict.

Root causes were an admission-time-only dependency check and inconsistent orphan
receipt checks between execution and status. The repair replays/authenticates the
exact committed coder A result before downstream stages, immediately before their
callbacks after durable intent, and before final report publication. These checks
cannot invoke coder A. Completed intermediate results remain committed; restored
valid evidence resumes only remaining stages. Orphan receipts now fence both run
and status before an intent or provider call, including a v1 session containing an
unexpected weight receipt.

Six new regressions failed on the initial implementation: revocation after coder A
result commit, during coder B, during evaluator, and after a downstream intent;
receipt corruption during coder B; and receipt-without-intent replay. Failed logs
are `regression-controls-before-fix.log` and `regression-intent-boundary-before-fix.log`
in the same verification directory. The intent-boundary case extends the same
defect family to a current-authority change during durable bookkeeping.

After repair, all 45 focused tests passed in 5.602 seconds, with no skips, failures
or errors. The source remained unchanged during that run. Weight-binding-only 119-file map:
`13b33572341cde7db706ed5183510a59e69862f6e111d63f5e876109e152fd30`.
The focused inventory digest is
`98c1feb30c54a245b01a12390e4734dfadb9f9797fae3af07503f58cc12c9746`.
Exact source identities, executed test IDs and scope flags are in
`focused-after-review-result.json`; the log is `focused-03-after-review.log`.

The earlier 425-test combined result is retained for its earlier source identity.
It does not cover these repairs. The final combined gate and same-team
re-review are recorded below. There is still no actual weight loader, model
endpoint, model execution, model-quality measurement or independent verification.

## Final combined local validation

The repaired weight-binding and build-admission changes were independently
reviewed within the same engineering team, then combined without further source
edits. The final 121-file selection executed all 473 software tests (386 existing,
45 weight-binding and 42 evidence-admission tests), with zero failures, errors,
skips, expected failures or unexpected successes. Total local runner elapsed time
was 33.113 seconds on x86_64/Python 3.12.14. All selected source identities matched
before and after execution.

Source-map SHA-256:
`7dfff2dc84b43b9c3c35e0513c31052307ad71ce79f1211f59736bdfa446afe9`.
Executed-inventory SHA-256:
`a70ce5d187c262cddc1a0c31d363d6be54bcb103cb47eae3b7bea87d7207f348`.

The prior 386/8/6 native result belongs to source commit
`4847d90dca4266d42651a8b9538c3eeae8a423b1`. Native acceptance for this new
selection is a separate gate. The source-specific result will be recorded in a
subsequent technical checkpoint. No actual model loading, weight editing or
model-quality improvement was measured, and production host authentication and
live service integration remain unprovisioned.
