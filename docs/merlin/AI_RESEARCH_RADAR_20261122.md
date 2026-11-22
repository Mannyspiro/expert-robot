# Merlin research radar — 22 November 2026

Status: bounded review of selected public primary papers, plus draft code. Not a comprehensive paper census or reproduction of benchmark claims. No weights, host permissions, private conversations, network services, or production release configuration changed.

## Framing and baseline

Merlin has an actual privately tested ARM64 Studio-to-GGUF chat and restart path (CACE Actions 45073523009). A 3-case practice-prompt experiment stayed at 2/3 correct with one gain and one regression (CACE 45074201432). The OCI ARM64 runner did not have CUDA or a model-training stack (CACE 45078750147). Existing Merlin stores include ProjectRegistry, immutable ArtifactRef, knowledge graph, knowledge compression and typed PromptTask. This work adds to those rather than building competing storage.

The question is whether relevant evidence, useful past strategies and properly calibrated verifiers can improve completed multi-step tasks per unit RAM, context tokens and wall time. Changes need paired independent tests. A source-title match, synthetically passing unit test or plausible rationale is not proof of quality improvement.

## Paper shortlist and explicit transfer status

| Rank | Original paper (source, publication status) | Idea and limitation | Merlin consequence |
| --- | --- | --- | --- |
| P0 | [How Much Should an Agent Remember?](https://arxiv.org/abs/2611.26361) (Nov 19, 2026 preprint) | More memory can harm weaker models; lessons need provenance and model-specific selection. | Add a bounded relevant subset and compare against no-context/full-context on current 1.5B model. |
| P0 | [AdMem: Expectation-Grounded Procedural Memory](https://arxiv.org/abs/2611.20605) (Nov 16, 2026 preprint) | Step-level expected vs observed outcomes; unbounded memory can be worse than none. | Episode shortlist is unverified metadata only; NEXT: host-attested expected/observed evidence. |
| P0 | [Memory Control Signals Emerge Before Action in Long Horizon Agents](https://arxiv.org/abs/2609.27286) (Sep 2026 preprint; introduces PaMER) | Select historical evidence before each action, rather than replay whole context. Hidden-state probes are not integrated into Merlin. | New evidence_budget module uses deterministic source-pinned byte-range selection and existing PromptCompiler. This is not a PaMER reproduction. |
| P0 | [VerifierBench: Benchmarking the Generation of Executable Verifiers for LLM Agents](https://arxiv.org/abs/2610.28679) (Oct 2026 preprint) | A verifier may reject invalid inputs while incorrectly rejecting other valid solutions. | New verifier_calibration module requires canonical, alternative-valid and invalid controls. No model-authored verifier code is executed. |
| P1 | [MemRL: Self-Evolving Agents via Runtime Reinforcement Learning on Episodic Memory](https://arxiv.org/abs/2601.03192) (Jan/Feb 2026 preprint) | Two-stage relevance and utility selection; results depend on reliable feedback. | New episode_utility_router uses query-tag matching and Laplace ratio heuristic from existing ArtifactRefs. It is NOT reinforcement learning or calibrated success probability. |
| P1 | [Agentic Context Engineering](https://arxiv.org/abs/2510.04618) (ICLR 2026) | Incremental context playbooks prevent repeated summarization loss. | Reuse existing provenance-aware knowledge_compression and ReviewContext; NEXT: test curated lessons with source replay. |
| P1 | [Agentic Plan Caching](https://proceedings.neurips.cc/paper_files/paper/2025/hash/9549f7d06700f0966d5f938f1d11022a-Abstract-Conference.html) (NeurIPS 2025) | Reuse a plan skeleton but adapt to live environment; published savings may not transfer. | NEXT: cache key includes tool versions, model identity and environment facts; invalidation and cache miss tests required. |
| P1 | [Recursive Language Models](https://arxiv.org/abs/2512.24601) (Dec 2025, revised May 2026) | Externalize large input and recurse over bounded snippets. | NEXT: max-depth and max-call context subqueries over exact artifact references. |
| P1 | [From Reflection to Co-Evolution](https://arxiv.org/abs/2611.10382) (Nov 7, revised Nov 19, 2026) | Replay a source decision with and without a proposed memory before retention. | NEXT: counterfactual, same-environment memory utility test. |
| P1 | [PILOT in the Loop](https://arxiv.org/abs/2608.26530) (Aug 2026) | Supervisor can stop/redirect worker during a long run; harness changes need authority boundaries. | NEXT: independent evidence-backed interruption and resume through existing leases. |
| P1 | [MemRefine](https://arxiv.org/abs/2606.13177) (Jun 2026) | Storage budgeting with preservation of useful facts; judgment can be wrong. | NEXT: reversible, versioned compression, never silent memory deletion. |
| P1 | [Scaling Agentic Verifier for Competitive Coding](https://proceedings.mlr.press/v306/ma26av.html) (ICML 2026) | Discriminating counterexamples can outperform random tests. | NEXT: trusted sandbox with generated metamorphic tests and independently known-good controls. |
| P1 | [The Horizon Gap](https://arxiv.org/abs/2608.06663) (2026 survey) | Task duration, model context and cross-task persistence are distinct, and final outcomes can hide process failures. | NEXT: step-by-step progress receipts and restart fault injection in production plan. |
| P2 | [Benchmarking KV-Cache Optimizations](https://arxiv.org/abs/2607.05399) (2026 preprint) | Compression ratio cannot predict throughput/answer quality alone. | NEXT: real CPU-GGUF KV experiments across context length, peak RSS, latency, accuracy. |
| P2 | [FlashAttention-4](https://arxiv.org/abs/2603.05451) (MLSys 2026) | Blackwell GPU-specific attention kernels, not transferable to current CPU runner. | DEFER until GPU exists and compatible runtime installed. |
| P2 | [Self-Adapting Language Models (SEAL)](https://arxiv.org/abs/2506.10943) (2025) | Model-proposed train data and gradient-based weight updates. | Existing draft self_edit_data_proposer and qwen_lora_candidate paths; real Qwen training blocked by hardware, no model improvement claimed. |
| P2 | [Language Models Can Rewrite Their Own Weights](https://arxiv.org/abs/2611.21885) (Nov 2026 preprint) | Direct gradient-free edits on a 27B model, with weaker outcomes for smaller models. | Existing small synthetic weight-edit tests, not self-rewriting Qwen 1.5B. |

## Concrete new code (draft PR 205)

All built atop existing ProjectRegistry, ArtifactRef and PromptCompiler rather than adding another database.

- python/merlin/evidence_budget.py + tests/test_evidence_budget.py: exact artifact version and source SHA, untrusted source byte slices, deterministic task-match selection, required source fail-closed, explicit context byte cap, typed draft-only PromptTask output.
- python/merlin/verifier_calibration.py + tests/test_verifier_calibration.py: evaluates a trusted callable on canonical valid, alternative valid and invalid answers; catches always-reject and always-accept and reports both error directions.
- python/merlin/episode_utility_router.py + tests/test_episode_utility_router.py: pinned episode metadata with two-stage tag relevance and simple outcome utility. Feedback is explicitly marked UNVERIFIED; there is no automatic strategy execution or weight update.
- .github/workflows/merlin-evidence-budget-contract.yml: focused no-network unit checks and exact source identity receipts.

These are bounded translations of ideas, not faithful reproductions of their full model-based architectures.

## Predeclared acceptance experiment

Set of at least 10 independently authored tasks spanning coding, mathematics, CAD, source-retrieval, restart and evidence judgment. Compare (A) full context (existing), (B) source-pinned budget selection, (C) verified strategy cues + budget selection (only after feedback is authenticated). Freeze model, generation settings, tool permissions and evaluator, and score answer correctness, exact source coverage, false-valid-rejection rate, prompt tokens, first-token latency, peak RSS and per-task completion. Require no loss of correct tasks and >=20% input-context savings in intentionally redundant contexts to admit a context policy *for further review*. Record null and regression cases; do not infer a global production improvement from synthetic checks.

## Skeptical Scientist lenses

Simplex: deferred; relevance is not a barycentric mixture. N-ality: apply independent axes of context bytes, evidence identity, accuracy, memory lifecycle, time and permissions. Continuum: test resource/correctness curves across context budgets and workload lengths, not a single extrapolation. Fuzzy: not applicable to Boolean authority, verification or release gates. Sample scope and publication state differ across sources, and the list is selective rather than exhaustive.

Decision: source-level components remain research-only on the draft branch. No automatic deployment/merge, no new model training, and no authority expansion. Next discriminating step: real-model paired context and verifier benchmark followed by independent review.
