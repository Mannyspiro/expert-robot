# Merlin research handoff (synthetic demo only)

This implementation exports deterministic research tasks with originating commit and CI run identifiers, a canonical SHA-256 checksum, and explicit `execution_authorized=false` and `production_change_authorized=false` flags.

It **does not connect to Merlin's task registry**, schedule jobs, or run an AI model. The repository's searchable index did not establish a verified registry API. Integrate only after reading the actual registry schema and tests; do not build a parallel scheduler.

The checksum detects accidental modification but is **not a signature** or proof of trusted origin. A malicious actor who can edit both payload and checksum can rehash it. Production trust requires signed artifacts or authenticated storage, authorization, and an independent reviewer.

No real records, client details, secrets, production telemetry, or arbitrary prompt text are included. Artex is an LLM cybersecurity framework and Titan is an encryption scheme; neither is an agent. Both remain unqualified for production integration here.
