# Merlin production evidence gap register — 2026-11-21

Parent: docs/engineering/merlin-production-decomposition-20261121.md
Source branch: merlin/release-gate-evidence-20261121

## Observed
- GitHub Actions runs 44964126391 (release evidence) and 44964126368 (self-healing) reported failure. Release job 137029191058 returned no step summaries and job logs returned HTTP 404 BlobNotFound. Root cause is unknown.
- Direct git clone from the independent execution environment failed DNS resolution for github.com. This is an environment connectivity limitation, not a test result for Merlin.
- The release checker has a reproducible standalone harness at scripts/run_merlin_release_checks.py.
- The release workflow now uploads its JSON report even on failure when the runner reaches that stage. Artifact availability must be checked on the next run.

## What must exist before any pass claim
| Gate | Missing evidence | Next experiment | Acceptance |
| --- | --- | --- | --- |
| CI | runnable job step and full test report | inspect artifact for next commit, then run harness on same source | all intended jobs pass with retained evidence |
| Browser native socket | peer identity and access control test on intended host | start actual socket service and test authorized and unauthorized peers | authorized peer works; unauthorized fails |
| Browser recovery | persisted state and interrupted lease proof | terminate service mid-operation, restart | no unauthorized replay; state reconciles |
| Python compatibility | complete Studio suite on supported Python | Python 3.10+ native suite | intended tests discovered and pass |
| Model | actual offline model provider and real output | bind explicitly configured local model | nonmock answer with provider identity and timings |
| Persistence | durable conversation/evidence readback | restart after real task | same conversation and artifact hashes |
| UI | real browser rendering | open loopback /studio and exercise conversation | usable UI, no false model readiness |
| ZIP | clean-machine install and rollback | extract/verify/run/stop/rollback | no undeclared dependency, repeatable startup |
| Provider preservation | independent config and trust boundaries | compare before/after configs | no overwritten credentials, no expanded authority |

## Failure decision tree
1. No job steps or artifacts: runner provisioning / checkout / external workflow execution remains unproven; do not modify application tests to mask it.
2. Steps and report present: identify the first failing command and reproduce on exact source and Python version.
3. Unit suite passes but full native acceptance fails: isolate the failing native boundary and preserve its regression.
4. All tests pass but no real model: report engineering validation, **not** a functioning offline assistant.
5. All gates pass: submit evidence to independent review; only then consider merge/deploy with rollback.

## Stop and rollback
No auto-merge, no auto-deploy, no invented receipts, no reclassification of missing evidence as passed. Release checker is a reporting tool and not an authorization service.
