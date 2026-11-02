# Merlin Resource Inventory v1

Date: 2026-11-02
Scope: supplied Merlin v31 and unified v10 bundles, plus the current `Mannyspiro/expert-robot` PR #67 head.
Status: static source inventory complete; live runner capacity probe pending.

## Evidence inspected

- `merlin_sovereign_os_v31_complete_bundle 4.zip`
- `MERLIN_HERMES_CACE_MCFC_Unified_Bundle_v10.zip`
- Current PR #67 head: `38e65ee0106c575c9dde9700ef24ca1c362736e7`
- Latest CI run: [41517256635](https://github.com/Mannyspiro/expert-robot/actions/runs/41517256635)
- Latest live Kokoro run: [41517256576](https://github.com/Mannyspiro/expert-robot/actions/runs/41517256576)

## Source inventory

### Sovereign v31 archive

| File | Size | Lines / records | Notes |
|---|---:|---:|---|
| `merlin_v26_engine.py` | 137,318 bytes | 2,845 lines | Large integrated Python engine; imports NumPy, Matplotlib, Pillow and standard-library modules. Contains multiple research, model-adapter, geometry and simulation classes. |
| `M.E.R.L.I.N._Ultimate_Master_Package.py` | 28,191 bytes | 475 lines | HTTP server/dashboard and master-core package; imports NumPy plus standard library. |
| `M.E.R.L.I.N._Ultimate_Master_Package.py` / engine pair | — | — | Treat as separate entry points until an explicit import/API contract proves they are safe to combine. |
| `gen18_lean4_compendium.csv` | 30,788 bytes | — | Formalization/research input; not runtime model weights. |
| Two HTML interfaces | 2,927,190 bytes each | — | Large static interfaces; identical byte size in the archive. Inspect hashes before treating them as distinct builds. |

The archive contains source and UI assets, not a verified local inference model or runner hardware report. The large Python engine has heavy scientific dependencies and should not be imported into the small API process merely to expose one feature.

### Unified v10 archive — current research-miner package

- Current package path: `current/MERLIN_HERMES_v19/`
- Python package has no declared runtime dependencies in `pyproject.toml`.
- The included unit suite contains 10 pytest-style tests.
- Local verification: `python -m pytest -q` → **10 passed**.
- `python -m compileall -q merlin_research_miner tests` → **passed**.
- `python -m unittest discover -s tests -v` discovers zero tests because the suite uses pytest functions; CI should use pytest for this package.
- The research miner is therefore a promising lightweight process/service boundary; it is not evidence that the entire v26 engine is lightweight.

The unified archive also contains multiple historical CACE versions and research intake batches. Do not merge historical snapshots into the active runtime by filename or version number alone. Use manifests, source hashes, explicit API contracts and independent tests.

## Current repository qualification evidence

- PR #67 remains a draft PR; do not merge or promote based on these checks alone.
- Latest CI run 41517256635: `build-and-smoke` passed; `merlin-nouscoder-inference` was skipped by its workflow condition.
- Latest live Kokoro run 41517256576: `live-synthesis` passed.
- Thus Kokoro has a real synthesis smoke result on this revision. NousCoder local inference is still **not qualified by the latest CI run**.
- No live external provider credentials or provider benchmark are evidenced here.

## Hardware and model inventory: pending

The uploaded source archives do not establish live Avrea/OCI RAM, VRAM, CPU, disk, runner quotas, or whether the NousCoder/Kokoro model caches are present on the current runner. These values must come from a fresh runner-side probe. Do not infer hardware from the `8-vcpu` runner label.

## Architecture decision from this inventory

1. Keep the existing Merlin API and remote gateway as the stable boundary.
2. Keep the research miner as an optional lightweight sidecar/module; its dependency-free package is a better first candidate for constrained deployments than the full v26 engine.
3. Do not load the full v26 engine in the request-serving process until its dependency footprint, import time, memory, and concurrency behavior are measured.
4. Do not download another multi-gigabyte model until the live runner probe reports sufficient free memory/disk and cache state.
5. After the probe, choose a small local model by measured RAM/VRAM fit and held-out task quality; benchmark quantization variants rather than selecting by parameter count alone.

## Next ranked execution

1. Run `.github/workflows/merlin-resource-probe.yml` manually on Avrea. It records hardware/runtime capacity and model artifact inventory without downloading weights or exposing environment secrets.
2. Use that result to choose the smallest candidate model and a conservative context/KV-cache budget.
3. Run one bounded local inference smoke and record cold-start, warm-start, peak memory, tokens/sec and task pass/fail.
4. Only then add the isolated model supervisor and A→B→A hot-swap test.
5. Compare fixed local, fixed remote and adaptive routing on the same held-out tasks and resource budget.

## Guardrails

- No model weights are committed to Git.
- Never log prompts, API keys or environment secrets in the resource report.
- Model unload is allowed only when no active request lease exists.
- Per-session KV state must never cross user/session/model/tokenizer boundaries.
- No silent private-prompt fallback to a remote provider.
- Candidate generation may be automatic; model promotion requires independent verification, human approval, rollback and authority non-expansion.
