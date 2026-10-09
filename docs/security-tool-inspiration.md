# Public security tools: research inspiration

Source review: 2026-10-09. These are public primary sources, not installed dependencies or tested integrations. No public-target scans were performed. Review current per-component licenses and pin a revision before reusing code; public availability does not imply unrestricted redistribution. All future hands-on experiments require owned or explicitly authorized targets. Numerical CACE and formal qualification retain their existing gates.

| Tool and primary source | Capability to study | Proposed experiment and measurement |
|---|---|---|
| [AFL++](https://github.com/AFLplusplus/AFLplusplus) | Coverage-guided fuzzing and corpus reduction | Compare bounded grammar enumeration with coverage-guided discovery on our parser; unique minimized semantic disagreements per fixed CPU budget. |
| [OSS-Fuzz](https://github.com/google/oss-fuzz) | Continuous fuzzing harnesses | Adapt harness lifecycle to our local fixtures; replay rate and time to regression detection. |
| [mitmproxy](https://github.com/mitmproxy/mitmproxy) | HTTP interception and inspection | Record traffic from our local app, sanitize it, turn traces into offline parser fixtures; deterministic replay agreement. |
| [ZAP](https://www.zaproxy.org/) | Web application testing platform | Compare expected findings on a locally owned training app with contract violations; precision on seeded cases. |
| [CodeQL](https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/) | Source-to-sink data flow | Encode a local raw-input-before-normalization fixture; positive/negative rule recall on owned code. |
| [Semgrep](https://github.com/semgrep/semgrep) | Source-pattern static analysis | Derive a rule from minimized fixtures; false positives on safe canonical-path consumers. |
| [Ghidra](https://github.com/NationalSecurityAgency/ghidra) | Software reverse engineering framework | Compare source and recovered semantics of our compiled parser; uncertainty in recovered control flow. |
| [Nuclei](https://github.com/projectdiscovery/nuclei) | Template-based vulnerability checks | Study declarative test DSL design for local fixtures; reject implicit network destinations and nondeterministic matchers. No external templates executed. |

## Ranked compositions (hypotheses, not validated integrations)

1. **Minimized parser witness → regression → static rule.** Use the present bounded experiment first; then CodeQL/Semgrep fixtures. Measure semantic disagreement coverage separately from pattern matching.
2. **Local trace → sanitized corpus → fuzzing → contract extraction.** Combine mitmproxy capture of our app with AFL++ style generation. Check reproducibility, privacy filtering and input-language coverage before expanding the grammar.
3. **Owned compiled parser → recovered semantics → differential oracle.** Use Ghidra to study whether source-level constraints survive compilation; distinguish recovery uncertainty from an actual implementation mismatch.
4. **Declarative test case → evidence packet → mathematical obligation.** Borrow Nuclei's template idea while keeping execution offline. Candidate obligations are canonicalization idempotence, representation agreement and complete mediation. CACE may consume numerical experiments in its supported domain; parser proofs need a separate finite-state/Lean bridge.

## Current experiment

`scripts/experiment_parser_differential.py` records the complete input corpus, its hash, original disagreements, deletion-minimized witnesses, independent-oracle repair checks and deliberate mutation failures. See [parser contract](parser-contract.md). This is an experiment on a toy policy/router, not a claim about vulnerabilities in these tools or Python. Python's [URL parsing security guidance](https://docs.python.org/3.12/library/urllib.parse.html#url-parsing-security) explicitly separates parsing from validation.
