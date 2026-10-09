# Expert Robot / CACE cross-chat handoff — 2026-10-09

This is a repository-backed checkpoint to continue the project in another
ChatGPT/Codex session. Prefer fresh GitHub reads over this historical snapshot.

## Canonical sources and authority policy
- Working repo: `Mannyspiro/expert-robot`, PR #47, branch `research/magick-ir-v0-1`.
- Target CACE repo: `morganaspim/Cace-app` (separately qualified LeanCert bridge).
- Treat commit SHA, matching GitHub workflow run and individual receipt as
  required evidence before calling any proof, model or optimization qualified.
- Authority invariant: **Capability grows, authority never expands.**
  No unsupervised release, RSI promotion, credential extraction, live security
  probing or costly resource allocations. Lab security work remains offline or
  against explicitly authorized systems. Prefer free checks; gate Avrea by
  actual half-month credits and keep one heavy validation lane at a time.

## Recoverable completed implementation
- Differential parser harness: 5,660 toy inputs, 436 disagreements,
  9 minimized witnesses; 0 repaired violations on the bounded corpus.
  See `scripts/experiment_parser_differential.py` and
  `docs/parser-contract.md`. These are not real-parser Lean proofs.
- Security mediation work: bounded 5-node DAG minimum weighted guard cuts,
  plus source-to-sink fixtures. See `docs/security-research.md`.
- OpenAI math catalogue: 719 manuscripts indexed, 200 distinct formal
  declaration targets; 50 batches of four planned. **Not** 200 verified
  results. Two adapted exact rational L1 graph lemmas were integrated;
  their statement scope differs from the upstream PiLp theorem.
  See `docs/openai-math-formal-verification-strategy.md`,
  `formal/MathAI/Graph/L1Append.lean` and
  `scripts/plan_openai_math_formal_verification.py`.
- Formalized synthetic bio conservation, equilibrium and molecular curvature
  conditional lemmas. The last observed exact-head formal workflow passed,
  but empirical molecular Hessians/parameters remain unqualified.
- Biochemical exploration: exact stoichiometry, CRNT counterexamples,
  SBML/libSBML standards and independent solver cross-checks on synthetic
  examples. These do not establish biological truth, chemical synthesis or
  improved CACE performance.

## Current repairs made in this continuation
1. Commit `4dbd5a24fcc3f5e5f99f4ea908c573b286ce81e1`:
   `scripts/profile_openai_lean_closure.py` accepts legal Lean apostrophe
   module identifiers; still rejects malformed paths. Previous pinned
   upstream scan had 2 false syntax failures, zero missing source modules,
   and inspected 32,887 local Lean modules.
2. Commits `f4a56bd5dbbdd4a4ed75da010e3b4f9f884c7318`
   and `8fdcf3454fbe9f9f2b5d19d47a46bee018f39b21`:
   offline synthetic prime/malformed/missing import tests and mandatory
   regression before expensive upstream kernel replay.
3. Commit `067bda834f81bc4c8c4e894c6aa50854a24b4d18`:
   stale PR-47 queue worker records a safe superseded no-op; scope and
   assignment cancellation checks remain mandatory. Queue workflow
   passed on that head.
4. Published `BIOMD0000000051` pinned intake run `38002448162`
   failed **correctly**, not because of missing checkout: 40 libSBML
   consistency findings including three severity-ERROR `10541`
   kinetic-law dimensional mismatches. Artifact `11650150126`.
   Model remains quarantined. See `docs/biochemistry-research-program.md`.
5. This handoff and enriched diagnostic metadata were added after
   investigating the published-model error. Check new workflow results for
   the exact final head; the text alone is not validation evidence.

## Ranked actionable continuation
1. Observe exact-head `Pinned OpenAI Lean Kernel Replay`. Previous
   run `37989327769` stopped at false-positive Lean import grammar.
   Once the repaired scanner runs, resolve any **new** setup/compile failure
   without weakening pinning, independent checker or axiom allowlist.
   Record original upstream theorem type, kernel receipt and source digest.
2. Implement fail-closed machine-readable upstream V2/V3 receipts with
   exact target signatures and axiom allowlist validation, then advance
   cost-bounded one-target batches before claiming further formal results.
3. Investigate the exact three libSBML issue `10541` source locations and
   kinetics unit provenance on pinned BioModels sample. Keep quarantine
   until an explicitly scoped corrected-model candidate is independently
   tested. Do not silently fix upstream data.
4. Generalize exact reaction conservation beyond the toy network and
   bridge the proved left-nullspace condition to CACE discretization,
   including boundary-source and unit counterexamples.
5. Move from toy security/parser witnesses to a scoped finite-state
   relation theorem and test actual in-repository interfaces, retaining
   counterexamples and no live scans.
6. Compare CACE benchmarks and holdouts before any proposed RSI
   optimization or model/policy promotion. Never infer runtime speedup
   merely from a mathematical proof.

## Verification command shortlist
```sh
python3 tests/openai_math_lean_closure_smoke.py
python3 tests/research_ci_queue_smoke.py
python3 tests/parser_differential_smoke.py
python3 scripts/plan_openai_math_formal_verification.py --batch-size 4 -o /tmp/openai-proof-plan.json
```
The upstream kernel replay needs pinned GitHub Actions Lean dependencies;
the above local Python checks alone never establish Lean V2/V3.
