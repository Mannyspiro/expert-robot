# Immutable RSI qualification sources

Candidate qualification downloads collar evidence before checking out candidate
code. It verifies the selected successful run belongs to the collar workflow in
this repository, and checks that the artifact's `source_run_id` equals that run.
Every candidate checkout uses the verified artifact SHA rather than a branch tip.

For automatic qualification, the collar artifact's candidate SHA must equal both
the triggering `workflow_run.head_sha` and the source run's head SHA. Push collar
runs also bind their source branch to the requested candidate branch. This
rejects evidence accidentally collected from a moved branch after an older push.

Manual collar dispatch may execute the trusted workflow on main while evaluating
its `candidate_ref` input. Its workflow head SHA identifies the dispatcher, so
qualification requires that dispatcher to use the repository's default branch
and the exact trusted verifier/base commit. A matching workflow path on another
branch cannot authenticate a collar artifact. Manual qualification also requires
the requested candidate branch to resolve
to the artifact's candidate SHA before checking out that immutable SHA. A branch
that has already moved fails qualification. A move after resolution cannot change
the checked-out source. Such collar runs should use manual qualification with
their run ID and candidate branch; automatic events on main fail the candidate
branch guard.

The independent decision job checks the same artifact run ID and candidate SHA
again. Collar validation requires `--source-run-id` at every call site.

Local regression commands:

```sh
python3 tests/rsi_source_binding_smoke.py
python3 tests/collar_evidence_smoke.py
python3 tests/promotion_workflow_smoke.py
python3 tests/cace_source_binding_smoke.py
python3 tests/blind_generation_view_smoke.py
python3 tests/blind_candidate_smoke.py
```
