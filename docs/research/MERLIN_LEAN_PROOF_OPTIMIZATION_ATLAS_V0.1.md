# Merlin Lean Proof Optimization Atlas v0.1

**Status:** research-derived strategy specification; profiles are not yet benchmarked on this branch.  
**Scope:** Lean 4 / Mathlib proof engineering for Merlin's mathematics, geometry, equation-atlas, XMG and THTG work.

## Executive decision

Merlin should optimize proof *search and maintenance*, not merely minimize tactic count. A proof is promoted only when the exact theorem statement, assumptions, dependency chain, kernel check, axiom audit and reproducible build are preserved.

The most useful pattern across the recent Lean ecosystem is a layered proof pipeline:

1. Reuse a library theorem or a previously verified local lemma.
2. Reduce the goal with explicit, narrow rewriting.
3. Select a tactic from the mathematical structure of the residual goal.
4. Use general proof search only after deterministic reduction.
5. Measure the result against a baseline.
6. Audit the final declaration and all dependencies.

## Recent public proof-engineering evidence

- The Lean/Mathlib tactic documentation describes Aesop's configurable rule sets, priorities and search configuration. It also documents a cheaper `rfl_cat` path ahead of expensive search in a specific tactic pipeline, motivated by the cost of `simp`. This supports cheap-first, bounded search rather than running unrestricted automation on every goal: https://leanprover-community.github.io/mathlib4_docs/tactics.html
- The Mathlib paper index includes recent work on library maintenance, proof generalization and canonical structures for automated theorem proving. Merlin should learn reusable abstractions and library interfaces, not memorize only final scripts: https://leanprover-community.github.io/papers.html
- The public Mathlib formalization index lists recent work across category theory, number theory, algebra, logic, temporal logic and symbolic reasoning. This is a useful corpus for transfer tests: https://mathlib.org/papers.html
- The UW Math AI Lab project list includes work on stabilizing Lean generation, proof-producing computation and geometric measure theory. This supports separating proof generation from proof checking and testing on held-out problem families: https://ai.math.uw.edu/projects/summer-2026/
- A published Aristotle/Lean case study reports verified local helper lemmas while the main theorem remains open. Merlin must therefore evaluate the exact target declaration, not the apparent amount of successful formalization: https://arxiv.org/abs/2605.20120

## Tactic selection profiles

The companion `config/proof_search_profiles.v1.json` stores the initial profiles. They are hypotheses for benchmarking, not claims of universal optimality.

| Goal structure | First choices | Escalation |
|---|---|---|
| Definitional equality / structure | `rfl`, `exact`, `assumption`, `constructor` | `simp only`, `ext`, `funext` |
| Closed numerical facts | `norm_num` | explicit normalization lemmas |
| Polynomial identities | `ring` | `ring_nf` |
| Integer / natural linear arithmetic | `omega` | split cases or expose arithmetic facts |
| Ordered linear inequalities | `positivity`, `linarith` | `nlinarith` |
| Polynomial inequalities | `positivity` | `nlinarith` with explicit square-nonnegative facts |
| Coordinate geometry | reusable incidence lemmas, `simp only`, `ext` | `ring`, `positivity`, `nlinarith` |
| Library theorem application | `exact`, `apply`, `refine` | theorem search, then controlled Aesop |
| Search-heavy residual goal | targeted simplification | Aesop with explicit rule sets and bounded configuration |

### Optimization rules

- Prefer `simp only [lemma₁, lemma₂]` when the intended rewrite set is known. Use unrestricted `simp` only when its broader rewrite database is justified.
- Do not unfold a structure or definition if an existing theorem already exposes the needed property.
- For equalities of structures, use the declared extensionality theorem and solve component goals; avoid repeated manual coordinate expansion.
- For polynomial identities, use `ring` before more expensive nonlinear automation.
- For inequalities, try structural positivity and linear arithmetic before nonlinear arithmetic.
- Use `omega` for Presburger arithmetic over integers/naturals; do not route those goals through general real arithmetic.
- Use Aesop with explicit local rules and priorities. Record the rule set because a proof's behavior depends on the active search environment.
- Treat shorter code as a readability signal, not a performance result. Compare elapsed time and heartbeats.

## Lessons extracted from Merlin's current Lean corpus

### Exact rational geometry

The existing `formal/MathAI/Geometry/Exact.lean`, `Derived.lean` and `VectorDerived.lean` files provide useful examples:

- Polynomial identities such as dot-product commutativity and squared-distance symmetry are well matched to `ring`.
- Componentwise vector identities are naturally handled by `ext` followed by component simplification; `ring` is needed only for residual polynomial equalities.
- Nonnegativity is better stated through reusable positivity lemmas or explicit `sq_nonneg` facts than by repeatedly expanding the same expression.
- Derived lemmas such as `cross_zero_left`, `cross_self` and `squaredDistance_eq_dot_vecBetween` should become reusable theorem-graph nodes.

### THTG conditional and audit proofs

The repository's 2026-11-04 proof receipts record three successful Formal Qualification runs:

- `THTGConditionalTheorems.continuous_attains_finite_maximum`
- `THTGPrintedBetaAudit.no_positive_g_fixed_point`
- `THTGPageCurveAudit.pageEntropy_has_no_maximum_on_open_interval`

The receipts record compiled theorem declarations and an axiom audit. They are evidence for those exact declarations at their pinned commits—not a blanket validation of the physical model or of alternative equations. Preserve their assumptions and source hashes.

The page-curve counterexample pattern is particularly reusable: to refute an alleged maximum on an open interval, construct a strictly larger admissible point (for example, a midpoint between the candidate and the endpoint) and prove the strict inequality. This is a general proof *shape*; each application still needs its own monotonicity and domain proof.

### XMG rewrite laws

The existing `formal/MathAI/XMGComposition.lean` establishes function composition laws and a well-foundedness theorem for a natural-valued decreasing measure. Merlin should use this as the formal foundation for rewrite termination, then separately prove that each concrete AST rewrite decreases the declared measure. The abstract theorem does not itself certify the Python rewrite engine.

## New Merlin subsystem: Proof Strategy Observatory

Add an observation record for every candidate tactic sequence:

- theorem identifier and normalized statement hash;
- assumptions hash and mathematical domain tags;
- tactic sequence, local simp set and Aesop rule-set identifier;
- success/failure and exact failure stage;
- wall-clock time, Lean heartbeats and peak memory;
- Lean version, Mathlib revision, import closure and environment;
- source commit, source hash and final axiom dependencies.

Keep failed attempts. They reveal which goal features cause search blow-ups and prevent Merlin from repeatedly paying for known-bad strategies.

### Adaptive ranking

For a given goal family:

1. Start from the deterministic profile in the config.
2. Include only observations whose theorem and environment are provenance-complete.
3. Require at least three verified observations before adapting ranking.
4. Rank by verified success rate first, then median heartbeats and elapsed time.
5. Keep a fixed baseline and a held-out set to detect overfitting.
6. Promote only if the new strategy preserves the theorem statement and assumptions and has no reliability regression.

Do not infer tactic quality from a single successful proof or from source-code length.

## Formalization integrity gates

Every formal result must be classified separately as:

- statement compiles;
- proof term kernel-checks;
- no `sorry` / `sorryAx`;
- axiom dependencies enumerated;
- theorem assumptions match the intended mathematical claim;
- imported definitions and upstream theorems are identified;
- independent numerical or symbolic checks, where relevant;
- empirical/model adequacy, where relevant.

A theorem that depends on classical choice is not automatically invalid. Merlin should report the dependency accurately and judge it against the theorem's intended foundations. Do not reject all classical axioms indiscriminately.

## Implementation sequence

1. Preserve the current proof receipt format and add statement/assumption hashes where backward-compatible.
2. Add a proof-attempt observation schema and immutable append-only store.
3. Implement deterministic goal-family profiles from the companion JSON.
4. Add a benchmark harness that runs baseline and candidate scripts on the same pinned toolchain.
5. Add held-out theorem families: exact geometry, algebraic identities, linear/nonlinear inequalities, topology/compactness, discrete arithmetic and XMG rewrite laws.
6. Add theorem dependency graph extraction and reusable-lemma recommendations.
7. Add proof-minimization as a separate pass; never overwrite the original proof until the replacement passes all gates.
8. Connect the resulting evidence receipts to Merlin's hypothesis ledger and CACE qualification workflow.

## Acceptance criteria

- No proof strategy is called optimized without comparative measurements.
- No theorem is promoted because only helper lemmas compiled.
- No assumptions are silently strengthened or dropped.
- Every accepted optimization retains the original proof as a rollback baseline.
- The exact Lean/Mathlib versions and axiom dependencies are recorded.
- The proof searcher learns from failures as well as successes.

**Design rule:** capability grows, authority never expands.


## Newly announced Lean-formalized mathematics to mine

The following are recent public announcements and should be ingested as *claims with status metadata*, not treated as equally mature or independently settled results:

| Date / period | Result announced | Evidence boundary | Merlin mining target |
|---|---|---|---|
| 4 Sep 2026 | Complete Lean formalization of Fermat's Last Theorem (FLT) | Anthropic reports a 13-million-line development, 29,500 intermediate theorems in the final proof, three standard Lean axioms, and statement comparison with Mathlib. This formalizes the established Wiles proof; the novelty is the end-to-end formalization, not a new proof of FLT. | theorem DAG decomposition, shared intermediate lemma discovery, statement/proof file separation, natural-language theorem indexing, collaborative work queues, statement comparator, dependency reuse |
| 17 Oct 2026 | Lean formalization of an announced refutation of the Exponential Time Hypothesis | OpenAI reports the result and Lean formalization; it also says an expert group will examine and shepherd the result. Treat as an announced result under external scrutiny, not as a settled consensus theorem. | exact statement normalization, counterexample/contradiction structure, premise tracking, independent verification and status tracking |
| 19 Oct 2026 | Lean formalization associated with local smoothing, Kakeya and Stein restriction results | OpenAI reports an AI-derived proof based on a novel auxiliary PDE and public Lean artifacts. Track the three implications separately and preserve the analytic hypotheses. | PDE auxiliary-object construction, implication graph, function-space hypotheses, theorem reuse across dimensions, analytic estimate libraries |
| Oct 2026 | Complete Lean formalization of the Classification of Finite Simple Groups announced by Axiom | Listed by Lean FRO as an announcement; do not infer code size, proof architecture or review status without examining the actual artifact. | massive theorem dependency graph, finite-group API reuse, modular decomposition, build scalability |
| Sep 2026 | Stronger prime-gap bound of 186 with Lean formalization announced | Lean FRO lists the result; record exact theorem statement, quantifiers and proof artifact before treating it as a verified corpus item. | analytic number theory interfaces, sieve estimates, explicit constants, reusable finite combinatorics |
| Aug 2026 | Progress on a Riemann-zeta result / stronger proportion bound announced with Lean formalization | Reported as progress on a proportion of zeros on the critical line, not a proof of the Riemann hypothesis. | statement-faithfulness checks, analytic estimates, partial-result classification, counterexample/status distinctions |

Primary sources:
- FLT formalization report: https://www.anthropic.com/research/formalizing-fermats-last-theorem
- OpenAI October 2026 mathematics announcements: https://openai.com/index/building-scientific-understanding-with-academic-communities/
- Lean FRO announcement timeline: https://lean-lang.org/
- Curated Lean papers and projects: https://leanprover-community.github.io/papers.html and https://leanprover-community.github.io/lean_projects.html

### FLT-specific architectural lessons Merlin should adopt

The FLT report describes several concrete engineering choices that are more transferable than any individual tactic:

1. **Theorem DAG as the planning authority.** Each theorem node should have a statement, assumptions, dependencies, proof status and assigned work. Agents select tasks from unmet dependency nodes, not from a vague global prompt.
2. **Separate theorem statements from proof bodies.** Keep stable statement modules independent of proof implementation modules so that dependency consumers can compile against the interface without recompiling unrelated proof bodies.
3. **Natural-language theorem descriptions.** Index every theorem by both its Lean declaration and a concise mathematical description; use this for semantic retrieval and lemma reuse.
4. **Reusable intermediate results.** Before proving a new lemma, search the current project and Mathlib for a statement-equivalent or weaker/stronger reusable result. Record adaptation cost and assumptions.
5. **Bounded parallelism with shared state.** Parallel agents need a single authoritative task graph, explicit ownership/leases and append-only receipts. The FLT report notes early coordination failures before the shared platform improved work allocation.
6. **Statement comparator.** Compare the final Lean theorem against a separately normalized intended statement. Check quantifiers, domains, side conditions and definitions—not merely names or prose.
7. **Build-aware module boundaries.** Measure import closure and compilation cost; isolate expensive proof bodies and avoid making every consumer import a huge implementation module.
8. **Independent proof audit.** Preserve the final kernel check, axiom report, exact source revision and dependency graph.

These are architecture patterns from a reported large-scale formalization. They are not proof tactics, and Merlin must validate their benefit on its own repository before calling them optimizations.
