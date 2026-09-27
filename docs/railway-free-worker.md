# Railway Free Worker

Expert Robot treats Railway's `ssh railway.new` VM as a disposable **L1
preflight worker**, never as a qualification or promotion authority.

As of 2026-09-25, Railway documents the anonymous VM as 2 vCPU / 2 GB RAM,
identified by the caller's SSH key. Unclaimed boxes have a 24-hour claim
window and are deleted with their files if they are not claimed.

Railway documentation:
- https://docs.railway.com/pricing/free-trial#try-without-an-account
- https://docs.railway.com/sandboxes

## Compute ladder

```text
L0  local/static checks
 |
 v
L1  railway.new free VM       2 vCPU / 2 GB, 1 build job
 |
 v
L2  Railway sandbox/fork      isolated experiments/checkpoints
 |
 v
L3  Avrea 8-vCPU CI           normal repository qualification
 |
 v
L4  Avrea 32-vCPU             manual heavy qualification
 |
 v
Lean evidence + repository CI + authority contract + promotion gate
```

A failure at a cheaper level blocks escalation. A pass only means the candidate
is worth testing at the next level; it never grants authority.

## One-command preflight

From your own machine:

```bash
ssh railway.new
```

Inside the VM:

```bash
git clone https://github.com/Mannyspiro/expert-robot.git
cd expert-robot
git checkout feat/reuse-refactored-fishstick
bash ./scripts/railway-preflight.sh --bootstrap
```

The wrapper deliberately uses one build worker. The underlying preflight can
also be run directly:

```bash
ER_PREFLIGHT_MODE=cheap ER_PREFLIGHT_JOBS=1 bash ./scripts/preflight.sh
```

Modes:

- `cheap`: current strategy/benchmark guardrails plus runtime smoke.
- `targeted`: broader strategy and benchmark tests.
- `full`: full C++ build and CTest; use only when the VM has enough time.
- changed Lean files are checked sequentially with the repo-pinned toolchain.

Evidence is written to:

```text
build/preflight/preflight-summary.json
```

The evidence explicitly states that Railway preflight has neither qualification
nor promotion authority.

## Checkpoints and forks

For account-backed Railway Sandboxes, prepare dependencies once, checkpoint the
disk, and boot isolated workers from that checkpoint:

```text
bootstrap
  -> checkpoint CACE/Expert-Robot toolchain
  -> isolated checkpoint worker
  -> preflight
  -> keep failed worker for debugging / destroy passing worker
```

The repository includes a helper around Railway's sandbox CLI:

```bash
# Run from a machine where the Railway CLI is authenticated and linked.
bash scripts/railway-sandbox-lane.sh prepare

# Later: boot from the checkpoint, refresh the branch, and run cheap preflight.
bash scripts/railway-sandbox-lane.sh verify

# If verification fails, the sandbox stays alive:
bash scripts/railway-sandbox-lane.sh shell

# Manual cleanup:
bash scripts/railway-sandbox-lane.sh destroy
```

Equivalent Make targets are `make sandbox-prepare` and
`make sandbox-verify`.

This is useful for repeated experiments because each candidate starts from the
same filesystem state. GitHub remains canonical; useful source changes and
evidence must return to the repository.

## What belongs on the free worker

Good fits:
- C++ compile failures
- focused CTest runs
- changed-file Lean checks
- SQLite/strategy-memory tests
- bug sweeping
- small benchmark probes
- orchestration scripts

Poor fits:
- 4B+ local model inference
- full model training
- large parallel Mathlib rebuilds
- long-lived state that is not checked into or backed up outside the VM

The 2 GB memory ceiling is the reason the default preflight is deliberately
sequential.
