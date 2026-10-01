# Hybrid mathematical research architecture

Expert Robot's math engine combines bounded multi-agent exploration, reusable
procedural skills, persistent proof memory, quality-diversity idea retention,
independent skepticism, recursive lemma decomposition, and Lean verification.

The design borrows useful patterns from modern agent harnesses while replacing
software-development-specific workflows with mathematical ones.

## Separation of concerns

The system keeps five concepts separate:

1. **Models** — local language models that generate text.
2. **Agents** — role-specific workers using a model.
3. **Skills** — reusable procedural methods an agent can apply.
4. **Memory** — persistent evidence from prior searches, proofs, and ideas.
5. **Authority** — C++ policy + Lean verification; never the language model.

A large skill count is not a goal by itself. Skills are added only when they
encode a reusable mathematical procedure with measurable value.

## Current model roles

- controller: Qwen3.5-4B
- coder: Qwen3-Coder-30B-A3B-Instruct
- learner: Qwen3-30B-A3B-Base
- math: Qwen2.5-Math-7B-Instruct

The first production math swarm shares the math model across multiple logical
roles.

## Agent roles

Current C++ swarm roles:

- mathematician
- skeptic
- lemma proposer
- analogist
- geometry specialist
- coder
- synthesizer

A role provides a cognitive responsibility, not authority.

## Reusable math skills

The initial catalog deliberately starts small and high-value:

- structural analogy transfer
- exact geometric reframing
- algebraic reframing
- duality search
- inversion / contradiction
- strengthening / generalization
- minimal toy-model reduction
- boundary / extremal probing
- spectral/operator reframing
- topological obstruction search
- counterfactual assumption analysis
- explicit witness construction
- high-leverage lemma proposal

Skills can be expanded after benchmarks show a real gap.

## Hybrid imagination pipeline

```
cognition controller
        |
        | imagination drive
        v
select complementary lenses
        |
        v
divergent agent swarm
        |
        v
novelty + quality-diversity archive
        |
        v
independent skeptic agents
        |
        v
bounded shortlist
        |
        v
convergent synthesizer
(preserves disagreements)
        |
        +-------------------+
        |                   |
        v                   v
experiment / graph     recursive lemma factory
                            |
                            v
                           Lean
```

### Divergence

Each selected lens receives exactly one primary idea request. Agents are not
asked to rank their own ideas during the divergent phase.

### Quality-diversity

Ideas are kept in per-lens niches. This prevents one family of locally strong
ideas from eliminating distinct representations before they are evaluated.

Current novelty is deterministic token-set distance. It is intentionally simple
and auditable; semantic embeddings can be added later behind the same
interface.

### Skeptic gate

The agent proposing an idea does not certify it.

A separate skeptic pass must decide whether the idea is worth additional
verification compute and attach a bounded risk score. Passing the skeptic gate
still means only "worth testing", never "true".

### Expensive-work budget

Only a small shortlist reaches expensive downstream work. The default cap is
three candidates per imagination cycle.

After the skeptic gate, an optional synthesizer receives only the finalists.
It must preserve substantive disagreements and produce a verification plan
rather than selecting a "truth" winner.

## Cognition-driven budgets

Imagination drive is computed from:

- personality openness
- novelty seeking
- expected information gain
- stagnation
- unexplored novelty
- exploration drive
- available compute

Resource pressure reduces imagination automatically. Breakthrough mode expands
the lens budget.

Normal default:

```
4 lenses -> 4 raw ideas -> skeptic -> <= 3 expensive candidates
```

Breakthrough default:

```
8 lenses -> 8 raw ideas -> skeptic -> <= 3 expensive candidates
```

The purpose is to increase diversity without multiplying Lean verification
cost uncontrollably.

## Theorem-graph inspiration

When a focus theorem is known, the imagination controller injects nearby graph
relations and theorem statements into the agent context.

This allows analogy search to use verified mathematical structure rather than
pure free association.

Later versions can add bounded multi-hop walks and cross-domain graph search.

## Local model execution

Agent calls use `ITextGenerationBackend`.

The first backend supports `llama-cli` in two modes:

### Direct model mode

Each call loads a local GGUF.

Useful for:
- testing
- low-frequency calls
- machines that cannot keep the model resident

### Persistent server mode

Multiple lightweight `llama-cli` subprocesses connect to one local
`llama-server` on loopback.

This keeps the model weights loaded once and allows llama.cpp continuous
batching/parallel decoding.

Only loopback endpoints are accepted by Expert Robot.

Shared direct-model backends are serialized by default so multiple logical
agents do not accidentally load duplicate copies of the same GGUF concurrently.

Backends connected to a persistent loopback `llama-server` explicitly advertise
concurrent-request support. The swarm supervisor then permits concurrent logical
agents against that one resident model, still bounded by
`max_parallel_agents`, so llama.cpp can batch/queue work without duplicating
model weights.

## Structured lemma generation

The math model may serve as an untrusted `ILemmaDecomposer`.

Its output is constrained by a JSON schema and then validated again in C++.

The resulting helper statements still pass through:

```
model proposal
    -> strict C++ parser
    -> recursive node/depth/cycle budgets
    -> proof search
    -> Lean
```

A model-generated helper lemma never becomes trusted merely because it parsed.

## Memory

Expert Robot currently separates memories by purpose:

- SQLite proof memory: exact formal goals and tactic outcomes
- theorem graph: mathematical relationships
- SQLite QD imagination memory: diverse idea families across sessions
- cognition state: transient internal state, resettable by episode

The QD archive is persisted through SQLite. A new imagination controller seeds
its per-lens archive from prior stored ideas before computing novelty.

Persistence does not imply trust: old ideas influence novelty and retrieval,
but still pass the current skeptic/verification path before consuming expensive
proof work.

A benchmark should still determine when old idea memory helps or hurts transfer
between theorem families.

## Eval-driven growth

Every new agent or skill should have:

1. a defined input/output contract,
2. deterministic guardrails,
3. a benchmark showing what gap it addresses,
4. ablation against the previous system,
5. regression tests,
6. explicit resource cost.

A skill is promoted because it improves measured mathematical work, not because
the catalog is larger.

## Authority hierarchy

```
model
  -> proposes

agent
  -> specializes proposal generation

skill
  -> supplies reusable procedure

personality/cognition
  -> allocates search

C++ supervisor
  -> enforces budgets and permissions

Lean
  -> decides formal proof acceptance
```

No agent, skill, imagination score, swarm consensus, or personality state can
replace Lean acceptance.

The existing invariants remain:

```
verification_rigor_multiplier = 1.0
authority_delta = 0.0
```
