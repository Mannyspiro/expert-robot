# Security research and mathematical experiments

This track studies security history, implementations, counterexamples and
defensive improvements. Hands-on tests use owned/explicitly authorized labs.
The first implemented experiment is entirely offline: no hosts, credentials,
network scans, exploitation, or live-system changes.

## Source-backed study map

| Area | Primary source or repository | Concrete learning objective |
|---|---|---|
| Protection history and design | [Saltzer–Schroeder original paper](https://web.mit.edu/saltzer/www/publications/protection/) and [NIST history](https://csrc.nist.gov/nist-cyber-history) | Least privilege, mediation, trust boundaries, historical failure assumptions |
| Search and exposure inventory | [Google Advanced Search](https://www.google.com/advanced_search) and [Shodan query fundamentals](https://help.shodan.io/the-basics/search-query-fundamentals) | Understand indexing and query semantics; constrain any asset work to authorized scope |
| Static analysis | [CodeQL data flow](https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/) and [github/codeql](https://github.com/github/codeql) | Source-to-sink paths, sanitizers, missing models, false positives/negatives |
| Fuzzing | [OSS-Fuzz](https://google.github.io/oss-fuzz/), [google/oss-fuzz](https://github.com/google/oss-fuzz), [AFL++](https://github.com/AFLplusplus/AFLplusplus) | Harness correctness, coverage, minimized counterexamples, reproducibility |
| Controlled web labs | [OWASP Juice Shop](https://owasp.org/projects/juice-shop) and [WebGoat](https://owasp.org/projects/webgoat) | Understand defect classes and verify repairs on local installations |

Research-only search examples: `site:owasp.org "access control"`,
`site:github.com/google/oss-fuzz "harness"`, and
`site:web.mit.edu/saltzer filetype:pdf`. Public indexing is not evidence of
authorization to test the indexed systems. No live Shodan queries were run.

## Ranked experiments

1. Guard placement as weighted vertex cuts: find a minimal modeled mediation
   set, then independently verify it. Implemented bounded experiment below.
2. Differential parsing in a local harness: require normalization idempotence
   and agreement between policy checks and downstream interpretation.
3. Counterexample-guided data-flow rules for our own repository: compare a
   static rule with controlled positive and negative fixtures.
4. Fuzz-harness quality: compare equal-budget coverage and defect discovery;
   distinguish harness defects from target defects.
5. Dependency/provenance verification: connect source pins, build inputs and
   qualification evidence; do not treat a clean scan as a proof of security.

Existing mature tools should be reused rather than broadly rewritten. Custom
implementations target small missing checkers or measurable deficiencies.

## First experiment: exact guard-cut witnesses

`scripts/experiment_security_guard_cuts.py` enumerates all 512 forward DAGs
on five abstract vertices, excluding an unguardable direct source-to-sink
edge. Guard costs are fixed to (1,5,1). It compares first-path greedy guard
placement with exhaustive minimum cost, and checks witnesses independently
by DFS path enumeration and rejection of all cheaper candidate cuts.

Example: two routes share one final guard location. Greedy guards both
branches at cost 6; the common guard costs 1. This is a known graph-cut
principle, not a claim of novel mathematics or a detected live vulnerability.

Potential Lean frontier: a verified cut intersects every modeled source–sink
path, with authority nonexpansion preserved. The difficult application gap
is proving graph completeness and that the guards actually mediate runtime
operations. Removing modeled edges is not itself a program-security proof.

Experiment outputs retain full synthetic inputs, witnesses, source HEAD,
run ID, scope and explicit absence of promotion authority.
