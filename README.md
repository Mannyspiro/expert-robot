# Expert Robot

Expert Robot is a local, modular AI research system designed around a thin Python orchestration layer and a C++ runtime core.

## Architecture

- **Python**: orchestration only
  - task routing
  - process supervision
  - experiment scheduling
  - generation lifecycle
  - promotion/rejection decisions from measured results
- **C++**: everything performance-critical and trusted
  - artificial interoception + software neuromodulation + personality executive
  - model adapters / inference backends
  - tool execution
  - sandbox interfaces
  - benchmark runner
  - verification hooks
  - artifact/state storage
  - telemetry
  - policy enforcement
  - model lifecycle helpers

## Initial model roles

1. **Controller** — Qwen3.5-4B
2. **Coder** — Qwen3-Coder-30B-A3B-Instruct
3. **Learner** — Qwen3-30B-A3B-Base
4. **Math specialist** — Qwen2.5-Math-7B-Instruct

Model weights are not committed to Git. Exact revisions and local paths belong in configuration.

## Core safety invariant

Capability may improve, but authority does not automatically expand.

Candidate self-improvements must pass:

```
propose
  -> sandbox
  -> test
  -> benchmark
  -> verify
  -> compare with parent
  -> retain or reject
  -> human/policy promotion gate
```

No candidate generation may silently gain filesystem, network, credential, process, or repository authority.

## Repository layout

```
expert-robot/
├── CMakeLists.txt
├── config/
│   └── models.example.json
├── cpp/
│   ├── include/expert_robot/
│   │   ├── cognition/
│   │   │   ├── controller.hpp
│   │   │   ├── interoception.hpp
│   │   │   ├── neuromodulation.hpp
│   │   │   └── personality.hpp
│   │   ├── protocol.hpp
│   │   └── runtime.hpp
│   └── src/
│       ├── main.cpp
│       └── runtime.cpp
├── python/
│   └── orchestrator.py
└── tests/
    └── smoke.py
```

## Cognition control loop

Expert Robot now has an objective internal-state loop:

```
runtime / proof / theorem-graph telemetry
                  |
                  v
       artificial interoception
                  |
                  v
      normalized cognitive signals
                  |
                  v
       software neuromodulators
                  |
                  +--------------------+
                  |                    |
                  v                    v
        transient affect        logical assessment
                  |                    |
                  +---------+----------+
                            |
                            v
                 personality executive
                            |
                            v
                   cognitive action
                            |
                            v
              math / code / research agents
                  |
                  v
                 Lean
```

Interoception measures resource pressure, proof/search stagnation, novelty,
surprise, uncertainty, route repetition, and verified progress. Software
neuromodulators turn those measurements into exploration, persistence,
attention, strategy-switch, and compute-conservation biases.

The initial personality is deliberately **high-openness + high-skepticism**:
creative enough to search distant representations while demanding external
evidence. It can select actions such as continue, explore, decompose, seek a
counterexample, generalize, compress, switch representation, intensify
verification, or conserve compute.

The integrated `CognitionController` performs the entire deterministic step:

`sensors + logic -> interoception -> neuromodulation -> personality -> action`

These cognition modules may change **how the system searches**, but cannot
change **what counts as verified**. Lean qualification and authority boundaries
remain fixed.

See `docs/artificial-interoception.md`,
`docs/software-neuromodulators.md`, and
`docs/personality-executive.md`.

## IPC

Python and C++ communicate over newline-delimited JSON on stdin/stdout.

This keeps:
- the Python surface small,
- the C++ runtime independently testable,
- the model/tool boundary explicit,
- future sandboxing straightforward.

## Build

```bash
cmake -S . -B build
cmake --build build -j
python3 python/orchestrator.py --runtime ./build/expert_robot_runtime
```

The first milestone is a working controller -> C++ runtime request/response loop. Model backends are added behind C++ interfaces after that boundary is proven.
