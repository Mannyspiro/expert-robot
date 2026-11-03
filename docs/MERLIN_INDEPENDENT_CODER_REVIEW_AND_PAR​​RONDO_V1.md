# Merlin Independent Coder Review and Hybrid Strategy Experiments v1

## Purpose
Use independent implementation and review roles to reduce correlated mistakes while keeping acceptance evidence-based. The reviewer must not be the author of the candidate patch.

## Two-coder protocol
1. **Spec owner** writes acceptance criteria, invariants, resource ceilings, and prohibited behavior before coding.
2. **Coder A** implements the smallest coherent change and supplies tests plus a concise rationale.
3. **Coder B** independently reads the specification and changed code. B first writes a review without relying on A's rationale, then checks edge cases, failure modes, dependency assumptions, and test quality.
4. **Adversarial test pass** adds tests for the review findings. B may propose patches but cannot self-approve them.
5. **Integrator** compares both proposals against the same tests and selects the smallest correct patch. If unresolved, keep the existing behavior and mark the issue open.
6. **Qualification** requires independent test execution, measured resource impact, artifact/commit identity, rollback reference, and explicit approval.
7. **Promotion** is a separate action. A green test run alone does not authorize runtime activation.

## Hybrid / poly-strategy experiments
If “Perrondo” means Parrondo-style alternation, treat it as an experiment family rather than an assumption. Compare:
- strategy A alone;
- strategy B alone;
- a fixed alternating schedule A/B;
- a state- or context-conditioned schedule;
- a simple non-hybrid baseline.

Use identical workloads, seeds, resource limits, and evaluation sets. Report mean and dispersion across repeated runs, quality, latency, peak RSS, load overhead, fallback rate, and failure rate. A hybrid is useful only if it beats the best single strategy on a predeclared objective without violating any hard quality or safety gate. Avoid selecting on one lucky run.

## Candidate ranking
Hard gates first: correctness, scope authorization, verifier pass, compatibility, memory ceiling, rollback availability, and no authority expansion. Only eligible candidates are scored. Use a Pareto frontier across quality, latency, resident memory, disk size, energy (if reliably measured), and maintenance burden. Do not collapse incomparable trade-offs into a single opaque score.

## Separation of roles
- Implementer: writes code.
- Reviewer: independently inspects and challenges code.
- Verifier: runs deterministic tests and independent checks.
- Integrator: decides whether the patch meets the spec.
- Promoter: explicitly authorizes activation after qualification.

These may be separate model instances or separate providers. Merely changing the prompt of one agent is not strong independence. Record provider/model/version, prompt/spec hash, commit SHA, and review result where available.

## Resource policy
Default to static checks and focused unit tests. Use the Avrea runner only for bounded benchmarks or integration tests that cannot be established locally. Do not download models as part of code review. Cache artifacts and pin all versions.

## Governing invariant
**Capability grows, authority never expands.**
