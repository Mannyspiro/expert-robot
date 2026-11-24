# Merlin bounded research queue — implementation checkpoint

The `research_queue.py` module converts synthetic security-event summaries into deterministic, bounded investigation tasks. It does not launch Merlin, call an LLM, execute tests, run Artex, deploy fixes or modify credentials.

Every task contains a stable identifier, priority, falsifiable hypothesis, synthetic reproduction test and independent-review requirement. Production or unclassified telemetry is rejected. Findings are proposed investigations, not confirmed vulnerabilities.

## Intended next integration
Connect the queue to Merlin's existing task/plan registry after verifying its actual API and schema. Do not create a parallel autonomous scheduler. Store the originating commit, CI run and task evidence in the canonical ledger. Keep a hard cap on research tasks and preserve human approval before any production change.

## Framework dependencies
Artex is an LLM cybersecurity framework and Titan is an encryption scheme, neither an AI agent. Their actual source versions, interfaces and security properties remain unverified here. Do not claim they are active.
