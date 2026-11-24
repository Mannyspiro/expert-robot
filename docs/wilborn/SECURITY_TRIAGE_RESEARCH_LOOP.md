# Bounded security triage and Merlin research loop

This milestone ranks **synthetic demo telemetry** deterministically. It does not perform autonomous threat hunting or implement Artex.

## Evidence boundary
Inputs are category counts only; never prompts, customer information, credentials, source IPs or raw logs. Results are candidate investigation tasks, not confirmed vulnerabilities.

## Proposed Merlin cycle
1. Observe approved synthetic telemetry and preserve the source commit and test run.
2. Rank findings by explicit priority and count; cap work to six findings.
3. Reproduce in isolated fixtures; propose one bounded hypothesis and falsifier per finding.
4. Research and patch in a review branch; test the original failure and negative cases.
5. Require independent security verification and human approval before merging or deploying.

No live secret rotation, unapproved security bypass, production code self-modification or unrestricted network probing. If Artex is unavailable, the existing business-tool boundary remains deny-by-default. Titan remains an unqualified cryptographic scheme until its implementation and security properties are independently verified.

## Limitations
Event counts alone cannot establish attack severity or causality. A priority is a review ordering, not an actual risk assessment. No real-client data is accepted.
