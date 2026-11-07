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
  - recursive Lean lemma decomposition and retry
  - bounded agent swarm + reusable math skills
  - quality-diversity imagination + independent skeptic gate
  - persistent local model-server supervision
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
│   │   │   ├── lemma_factory_bridge.hpp
│   │   │   ├── neuromodulation.hpp
│   │   │   └── personality.hpp
│   │   ├── imagination/
│   │   │   ├── archive.hpp
│   │   │   ├── controller.hpp
│   │   │   ├── idea.hpp
│   │   │   └── memory.hpp
│   │   ├── research/
│   │   │   ├── candidate_verifier.hpp
│   │   │   ├── engine.hpp
│   │   │   ├── episode_ledger.hpp
│   │   │   ├── knowledge_consolidator.hpp
│   │   │   └── state_machine.hpp
│   │   ├── skills/
│   │   │   ├── experimental_skill_store.hpp
│   │   │   ├── math_skill.hpp
│   │   │   ├── model_skill_proposer.hpp
│   │   │   └── skill_ledger.hpp
│   │   ├── eval/
│   │   │   └── math_eval.hpp
│   │   ├── swarm/
│   │   │   ├── agent.hpp
│   │   │   ├── aggregator.hpp
│   │   │   ├── supervisor.hpp
│   │   │   └── task.hpp
│   │   ├── formalizer.hpp
│   │   ├── lemma_factory.hpp
│   │   ├── model_formalization_proposer.hpp
│   │   ├── model_lemma_decomposer.hpp
│   │   ├── model_server.hpp
│   │   ├── text_generation.hpp
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
             +--------------+--------------+
             |                             |
             v                             v
       ordinary search             DECOMPOSE_PROBLEM
             |                             |
             |                             v
             |                   recursive lemma factory
             |                             |
             |                     proven child lemmas
             |                             |
             +--------------+--------------+
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

When the personality executive selects `DECOMPOSE_PROBLEM`,
`CognitionLemmaBridge` invokes the bounded recursive lemma factory. The factory
tries smaller helper lemmas, accepts only Lean-proven child declarations into
the retry context, and then retries the parent theorem.

These cognition modules may change **how the system searches**, but cannot
change **what counts as verified**. Lean qualification and authority boundaries
remain fixed.

See `docs/artificial-interoception.md`,
`docs/software-neuromodulators.md`, `docs/personality-executive.md`, and
`docs/recursive-lemma-factory.md`.

## Hybrid mathematical research engine

The cognition system now controls a bounded research swarm instead of routing
every hard problem to a single prompt.

```
personality + interoception + neuromodulation
                    |
                    v
             imagination drive
                    |
                    v
        complementary math skills/lenses
                    |
                    v
            divergent agent swarm
                    |
                    v
       novelty + quality-diversity archive
                    |
                    v
          independent skeptic gate
                    |
              <= 3 candidates
                    |
          +---------+----------+
          |                    |
          v                    v
   experiment/graph     recursive lemma factory
                               |
                               v
                              Lean
```

Agents and skills are deliberately separate. An **agent** is a specialist
worker; a **skill** is a reusable mathematical procedure that can be applied by
a worker. The initial catalog includes analogy transfer, geometry/algebra
reframing, duality, contradiction, generalization, toy-model reduction,
boundary probing, spectral/topological reframing, counterfactual analysis,
explicit construction, and high-leverage lemma generation.

For efficient local inference, Expert Robot can launch one persistent,
loopback-only `llama-server` for Qwen Math. Lightweight agent subprocesses
reuse those resident weights. Direct GGUF-per-call mode remains available for
testing.

The local model is still untrusted: imagination proposes, the skeptic filters,
C++ enforces budgets/contracts, and Lean decides formal proof acceptance.

See `docs/hybrid-math-engine.md`.

## Verified research episodes

The C++ `MathResearchEngine` now runs a bounded formal-mathematics episode:

```
formal target
  -> retrieve
  -> direct proof
  -> cognition
  -> imagination and/or recursive lemmas
  -> skeptic-approved idea formalization
  -> helper verification
  -> parent retry
  -> target verification
  -> theorem-graph consolidation
  -> hash-chained episode lineage
```

Helper lemmas do **not** complete the episode. Only target-level proof
verification can move the research state to consolidation/completion.

The engine also includes:

- bounded multi-hop theorem-graph inspiration,
- experimental-vs-qualified skill stages,
- model-proposed skills isolated in an experimental store,
- evaluation-only experimental-skill overlays,
- per-skill outcome telemetry,
- baseline-vs-candidate math ablations,
- strict informal-to-formal theorem-statement proposals,
- verified theorem-graph persistence, and
- tamper-detecting SHA-256 event chains.

See `docs/research-engine.md`.

## Compute ladder and cheap preflight

Expert Robot uses a fail-fast compute ladder so expensive qualification runners
are reserved for work that already passed cheaper checks:

```text
L0 local/static
 -> L1 railway.new free VM
 -> L2 Railway sandbox/checkpoint/fork
 -> L3 Avrea 8-vCPU CI
 -> L4 Avrea 32-vCPU manual qualification
 -> Lean evidence + repository CI + authority/promotion gate
```

Railway preflight can reject a candidate, but a pass never grants qualification
or authority. The machine-readable contract is
`config/compute_policy.json` and CI enforces its authority boundaries with
`tests/compute_policy_smoke.py`.

On a Railway free VM:

```bash
ssh railway.new
git clone https://github.com/Mannyspiro/expert-robot.git
cd expert-robot
git checkout feat/reuse-refactored-fishstick
bash ./scripts/railway-preflight.sh --bootstrap
```

The 2 GB worker defaults to one build job and sequential focused tests. See
`docs/railway-free-worker.md` for the operating model.

## Merlin Virtual GitHub Forge

Merlin's primary development control plane is the local SQLite-backed Virtual
Forge, not GitHub pull requests. It provides content-addressed commits,
branches, internal pull requests, three-way merge/conflict detection, rollback,
a hash-chained event log, and a leased worker-job queue. GitHub is an optional
remote adapter for exchange and provenance.

The initial Forge implementation and command interface are:

- `python/virtual_forge.py`
- `python/forge_cli.py`
- `docs/virtual-github-forge.md`

Run the Forge contract tests with:

```bash
python3 -m unittest discover -s tests -p 'test_virtual_forge.py' -v
```

The Forge records jobs and evidence but does not execute untrusted code in its
database process. A dedicated, resource-limited worker runtime and independent
CACE verification remain required before worker results can be promoted.

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

The runtime/controller boundary, local model interfaces, verified proof loop,
cognition stack, swarm, skill governance, recursive lemma search, and bounded
research engine are now implemented behind C++ interfaces. The next milestones
are benchmark corpus expansion, real local-model qualification runs, and
measured promotion of only the capabilities that improve Lean-verified results.
