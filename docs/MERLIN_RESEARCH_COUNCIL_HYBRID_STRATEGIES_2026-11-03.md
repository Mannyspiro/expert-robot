# Merlin Research Council: Hybrid Coding and Strategy Selection

Date: 2026-11-03
Scope: independent code review, strategy switching, and evidence-based promotion.

## Council question
Should Merlin use multiple coding agents and Parrondo-inspired hybrid strategies?

## Research inputs

1. **Multi-agent software engineering experience report (2026).** The study reports broadly comparable recommendation effectiveness across evaluated frameworks, but substantial efficiency differences (including token and execution-time costs). This argues for a small, role-specialized council with explicit budgets rather than maximizing agent count.
   - https://link.springer.com/article/10.1007/s10664-026-10955-8

2. **Human-AI agentic code review (2026).** Analysis of 278,790 review conversations reports that human reviewers add contextual feedback; AI suggestions were adopted at a lower rate and could increase code complexity when accepted. This supports human/integrator authority and tests that challenge reviewer suggestions rather than auto-applying them.
   - https://arxiv.org/abs/2603.15911

3. **AI-to-AI code review dataset (ESEM 2026).** Cross-product review exists at scale, but observed review patterns vary across author/reviewer pairs. Different providers may diversify errors, but provider diversity alone does not establish correctness.
   - https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESEM.2026.75

4. **Parrondo-inspired network routing (Physical Review Research, 2024).** The paper reports a routing result where switching between shortest-path and greedy local routing can outperform either standalone strategy on its studied network objective. This is a proof of possibility in a particular domain, not evidence that alternating coding agents will improve code.
   - https://journals.aps.org/prresearch/abstract/10.1103/PhysRevResearch.6.L012037
   - Foundational explanation: https://www.nature.com/articles/47220

## Council positions

### Builder
A second coder can produce alternative implementations and broaden solution search. The strongest use is parallel proposals against one frozen specification, followed by a common test harness. It should not be asked to merely endorse the first implementation.

### Skeptic
Agent consensus can be correlated: models may share training data, assumptions, and blind spots. More agents increase latency, token cost, and integration complexity. A reviewer can confidently propose an incorrect refactor. Therefore, count independently reproduced findings, not votes.

### Performance researcher
Hybrid strategies deserve a controlled experiment when workload state changes over time (for example, fast heuristic versus slower high-quality route). Compare each strategy alone, fixed alternation, randomized alternation, and a context-conditioned selector on paired seeds. Measure quality, tail latency, memory, switching overhead, and failures. Switching is worthwhile only when the combined policy beats the best standalone policy under a predeclared objective.

### Verifier
Tests, static checks, reproducible benchmarks, artifact hashes, and rollback references outrank persuasive debate. The council may nominate a candidate; it cannot waive a failed gate.

### Integrator decision
Adopt a **small heterogeneous council**:
- Implementer: proposes one minimal patch.
- Independent challenger: creates a separate review and adversarial tests before reading the implementer's rationale.
- Performance analyst: measures resource/quality tradeoffs.
- Verifier: runs deterministic tests and checks invariants.
- Integrator: reconciles findings and records dissent.
- Human maintainer: retains merge and promotion authority.

Use a different model/provider for the challenger when practical. Record provider/model/version, prompt/spec hash, candidate commit, review findings, and tests. If provider diversity is unavailable, label the review as a separate pass, not an independent external review.

## Parrondo-inspired experiment protocol

Baseline strategy set:
- A: compact core only.
- B: specialist-heavy / high-quality route.
- A→B: deterministic alternation on a predeclared schedule.
- Contextual: select A or B using observable task/resource state.
- Hybrid fallback: start with A; escalate to B only on a defined uncertainty or verifier trigger.

All strategies must receive the same tasks and seeds. Include switching/load costs. Report mean and dispersion plus p50/p95 latency where available. The experiment is inconclusive if the sample is too small or confidence intervals overlap materially. Never infer a Parrondo effect from a single workload or a single lucky run.

## Promotion rule

A strategy is eligible only if:
- quality floor and verifier requirements pass;
- no unresolved correctness or security findings remain;
- memory/resource budgets are respected;
- rollback is available and tested;
- its measured improvement exceeds the best standalone baseline by a predeclared practical margin;
- authority and permissions do not expand.

Pareto-incomparable candidates remain alternatives; do not hide tradeoffs in a single opaque score. This document records research inputs and a decision protocol, not a claim that a hybrid has already won.

**Capability grows, authority never expands.**
