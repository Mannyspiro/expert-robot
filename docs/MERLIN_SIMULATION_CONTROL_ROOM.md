# Merlin Simulation Control Room

## Run it

From the repository root:

```bash
PYTHONPATH=python python3 -m merlin.app --port 8765
```

Open `http://127.0.0.1:8765/hud`. The server binds to loopback only. The HUD uses the same API as programmatic clients and needs no external JavaScript packages, CDN, hosted database, or paid visualization service.

## What the HUD shows

- Task progress, confidence, uncertainty, simulated CPU/memory, queue depth, active agents, hypotheses, and verified-claim count.
- Research pipeline state: observe → hypothesize → experiment → verify → consolidate.
- A decision trace that shows the current simulated policy recommendation and the measured state values that triggered it.
- Time-series plots drawn directly from the simulator's metric samples.
- A reverse-chronological event stream with explicit `source=simulation` labels.
- Operator controls for advancing, pausing, resuming, verifying, decomposing, exploring, compressing, injecting uncertainty, and resetting.

## API

- `GET /hud`: responsive control-room UI.
- `GET /api/sim/state`: complete current simulation snapshot, world graph, decision preview, metrics, and recent events.
- `GET /api/sim/events`: recent simulator events.
- `POST /api/sim/step`: advance the simulator with one bounded action.

Example:

```bash
curl -s http://127.0.0.1:8765/api/sim/state
curl -s -X POST http://127.0.0.1:8765/api/sim/step \
  -H 'Content-Type: application/json' -d '{"action":"inject_uncertainty"}'
```

Allowed actions: `advance`, `pause`, `resume`, `inject_uncertainty`, `verify`, `decompose`, `explore`, `compress`, `reset`. Unknown actions are rejected. A paused simulation cannot advance until resumed. Reset returns the world to initial conditions.

## Data truth and boundaries

The first environment is deliberately deterministic and synthetic. The API marks every snapshot with `environment=deterministic_simulation` and `simulation_only=true`. Metrics are real measurements of the simulator's own state, not claims about host CPU, real model inference, or production agents. Decision traces explain the simulator's policy, not private model thoughts.

The simulator has no shell, filesystem, network, credentials, deployment, or repository write capability. It does not call a model. Real runtime telemetry and model-generated reasoning will be added as separate source-labeled event streams after their adapters are connected and qualified. The HUD must never silently blend real and simulated measurements.

## Extension contract

Use versioned events as the integration boundary. Future runtime adapters should publish typed events with source, timestamp, run ID, task ID, model/provider identity where applicable, duration, resource usage, evidence references, and status. Visualization components should subscribe to normalized events and derive views from them rather than inventing their own state. Model reasoning should be labeled as model output and linked to its prompt/spec and response hashes.

The invariant remains: **capability grows, authority never expands.** The HUD is observability and simulation control, not an authority console.
