# Loader qualification harness v1

## Purpose

The CPU-fabric loader now has an evidence-only qualification harness at
`python/merlin/cpu_fabric/qualification.py`. It measures repeated cold activation,
warm resident activation, and unload operations. The harness never sets manifest
approval, changes routing policy, or authorizes promotion.

## Measurements

Each operation records elapsed wall time and samples process RSS using Linux
`/proc/self/statm` at a configurable interval. The report contains before,
sampled peak, after, peak delta, and retained delta values where available.
It also records resident accounting after unload and median cold/warm/unload
latencies.

## Interpretation limits

- Sampling can miss short-lived allocations between samples.
- RSS is process-wide, not attributable solely to the module.
- RSS may be unavailable outside supported Linux environments.
- Cold activation includes the catalog's current full-artifact read and hash.
- Warm activation is a resident lookup, not a second physical load.
- An empty resident set after unload does not prove the runtime released every
  native allocation; retained RSS is supporting evidence only.
- A declared RSS ceiling is evaluated only when all cold-load RSS samples exist.

The report deliberately returns `qualified: false` and
`promotion_authorized: false`. Qualification requires independent review,
held-out workloads, a predeclared ceiling and tolerance, repeated successful
cold/warm/unload/reload trials, and an explicit human decision. No automatic
approval or authority expansion is possible.

## Invocation

The harness is a Python API, not a deployment workflow:

```python
from merlin.cpu_fabric.qualification import run_loader_qualification

report = run_loader_qualification(
    manager,
    "module-id",
    trials=5,
    rss_ceiling_bytes=2_000_000_000,
    sample_interval_ms=5,
)
```

Persist the returned JSON report with the exact code commit, host/runtime
description, manifest digest, artifact digest, and test command when executed.
