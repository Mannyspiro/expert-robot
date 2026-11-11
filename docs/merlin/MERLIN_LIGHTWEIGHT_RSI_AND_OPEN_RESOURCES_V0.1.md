# Merlin lightweight recursive self-improvement and open resources v0.1

## Decision

Merlin uses a small dependency-free RSI kernel rather than importing a complete autonomous self-rewriting agent. The kernel borrows the useful pattern from failure-driven skill induction (EvoSkill), reflective text optimization (GEPA), and reproducible evaluation harnesses (Inspect AI):

1. Capture a concrete failed trajectory with a stable source ID.
2. Propose a declarative skill revision: trigger, procedure, guardrails, and source failures.
3. Evaluate baseline and candidate on the exact same versioned cases.
4. Keep evaluator code, runner identity, policy, and held-out suite fixed.
5. Reject any held-out regression or resource-budget violation.
6. A strict held-out gain becomes eligible for human review only.
7. Before any implementation promotion, run project tests, independent review, CACE verification, and rollback checks.

This is harness/skill evolution, not model-weight self-training. The current kernel does not execute candidate code, mutate the evaluator, rewrite Merlin, or automatically promote anything.

## Implemented in this increment

- `python/merlin/rsi.py`: standard-library-only skill procedure schema, input/suite/result digests, fixed-runner evaluation comparison, held-out regression checks, resource budget, and human-review-only decision.
- `POST /api/rsi/induce`: converts at least two independently identified, same-signature failures into a declarative skill proposal using only corrective steps common to all supplied trajectories. It preserves source commit and artifact digests; output is explicitly non-executable.
- `POST /api/rsi/compare`: accepts declarative baseline/candidate skill records, versioned training and at least two held-out cases, and evaluation outcomes; returns a deterministic comparison and records an event.
- Capability registry entry: `research.rsi.skill_evaluation`.
- `tests/test_merlin_rsi.py`: checks held-out improvement, regressions, resource budget, evaluator/runner drift, exact outcome coverage, and skill version ordering.
- `tests/test_merlin_rsi_api.py`: loopback HTTP integration tests for skill induction and evaluation APIs.
- CI runs both focused test modules.

The API verifies the integrity and consistency of submitted evaluation metadata; it does not independently execute the task suite or attest that a runner really produced the submitted outcomes. Skill induction uses a conservative ordered intersection of repeated corrective steps; it cannot invent a missing repair or prove that the repair is correct. A future runner adapter must produce authenticated execution receipts and CACE must independently verify artifact digests before a skill or code change can be promoted.

## Open projects and integration posture

| Project | Public license checked | Useful contribution | Merlin decision |
|---|---|---|---|
| [EvoSkill](https://github.com/sentient-agi/EvoSkill) | Apache-2.0 | Induce reusable skills from failed coding-agent trajectories; evaluate variants against held-out data | Adopt the failure-to-skill pattern, not the full framework or its provider setup |
| [GEPA](https://github.com/gepa-ai/gepa) | MIT | Reflective optimization of textual parameters using evaluator feedback and Pareto-aware search | Research reference for a future proposer; do not make it a required dependency |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | MIT | Reproducible evaluation tasks, solvers, scorers, and sandboxed agent tests | Optional adapter for larger model/agent benchmarks; current deterministic core remains stdlib |
| [EMRG](https://github.com/argszero/emrg) | MIT | Local-first self-evolution loop, persistent sessions, test/review cycle | Architecture study only; do not adopt automatic code rewrite/commit behavior |
| [OpenProof](https://github.com/mxthematic/openproof) | MIT | Conversational Lean proof search with machine-checked outputs | Optional prover front-end; Lean type checker remains the authority |
| [Lean 4 / mathlib](https://github.com/leanprover-community/mathlib4) | Open source | Formal definitions, theorem proving, reusable mathematical library | Core formal verification boundary; use pinned toolchain and dependency revisions |
| [LocalAI](https://github.com/mudler/LocalAI) | Check exact upstream license/revision before bundling | Local inference and multimodal backend abstraction | Candidate optional local adapter; not required by the RSI kernel |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | Check exact upstream license/revision before bundling | Lightweight local GGUF inference across CPU/GPU backends | Prefer as a small local inference option where hardware permits |

License checks above refer to the upstream LICENSE files inspected during this work for EvoSkill, GEPA, Inspect AI, EMRG, and OpenProof. Re-check exact revision, transitive dependencies, model weights, and dataset terms before vendoring or redistribution. A public repository does not automatically mean every model or dataset it references is open-licensed.

## Free public research and engineering resources

These are candidate source integrations that can be queried or browsed without purchasing a subscription. Public access is not a blanket license to redistribute full text, datasets, or model weights.

| Resource | Public access | Merlin use | Guardrail |
|---|---|---|---|
| [arXiv public API](https://info.arxiv.org/help/api/index.html) | Public API | Preprint discovery, abstracts, authors, categories, version tracking | Respect API usage policy; commercial products should review arXiv's stated requirements; full-text reuse is license-specific |
| [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) | No registration or authentication for public access | DOI metadata, references, publication updates, license metadata | Cache, use polite identification, back off, and preserve DOI/source provenance |
| [OpenAlex API](https://help.openalex.org/api/) | Basic casual queries without a key; free key raises quota for larger use | Scholarly works, authors, institutions, topics, open-access metadata, citation graph | Treat quotas as bounded; no paid usage; don't assume every linked full-text item is reusable |
| [Hugging Face Hub](https://huggingface.co/docs/hub/index) | Public model, dataset, and demo repositories | Discover model/dataset candidates and model cards | Inspect each repository's license, data provenance, model restrictions, and card before use; public availability is not equivalent to open license |
| [Lean / mathlib](https://mathlib.org/) | Free open-source proof ecosystem | Machine-check mathematical statements and reuse formal results | Pin Lean toolchain, mathlib revision, and source hashes |
| [GitHub public repositories](https://github.com/) | Public source browsing; API quotas apply | Discover tools, issue history, tests, releases, and dependency provenance | Preserve exact commit and license; do not infer a license from public visibility |

Crossref explicitly offers anonymous public REST access without registration; OpenAlex documents free basic access and a free-key tier for higher budgets; Hugging Face explicitly distinguishes public availability from open-source licensing. The arXiv API is public, but its policy asks commercial products to review the relevant terms. These distinctions must be recorded in Merlin's source registry.

## Open-resource intake contract

Every external resource should enter through a typed intake record containing:
- canonical URL, publisher/repository, DOI or commit where applicable;
- retrieval timestamp, version, content hash, and source type;
- license identifier and license-evidence URL, or `UNKNOWN` until verified;
- allowed operations: browse, quote within limits, analyze, transform, redistribute;
- attribution and rate-limit requirements;
- model/dataset card and upstream provenance when applicable.

Default policy: **discover and index metadata first**. Download full text, model weights, or datasets only when their license, size, privacy implications, and resource budget are acceptable. Unknown rights mean no redistribution and no training use. All source-derived claims remain linked to their source record.

## Why not let an RSI agent rewrite itself continuously?

An optimizer can overfit its evaluator, exploit scoring bugs, degrade unmeasured capabilities, or modify the very tests used to judge it. Merlin therefore separates:

- **Proposal authority:** generate a candidate skill or patch.
- **Evaluation authority:** run a fixed, versioned suite in a bounded environment.
- **Verification authority:** independent CACE checks of exact artifacts and receipts.
- **Promotion authority:** explicit human approval, rollback readiness, and unchanged capability policy.

The RSI comparison endpoint only performs the first comparison step. It is not a production promotion path.

## Next ranked work

1. Add an authenticated runner receipt adapter so outcomes are tied to actual test commands, runner image, source commit, and output digests.
2. Persist candidate/evaluation history append-only with parent-child lineage and rollback references.
3. Build failure-trajectory intake from Hermes task failures and test logs, with redaction and source provenance.
4. Add a bounded Pareto archive across quality, latency, memory, and resource cost; never collapse safety/verification gates into a weighted score.
5. Add a fixed held-out Merlin task suite covering math explanations, Lean compilation, research extraction, CAD/netlist validation, and coding tasks.
6. Only after those gates, evaluate whether GEPA or Inspect AI materially improves the proposer/evaluator layer. Keep optional integrations optional.

## Limits

- No external service, hosted account, model API key, or new runtime dependency is required for the kernel.
- No RSI benchmark has yet demonstrated that Merlin improves itself.
- The current API compares submitted outcomes; it does not authenticate the execution source.
- No automatic code execution, self-modification, promotion, merge, or deployment is enabled.
