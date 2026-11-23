# Wilborn automatic security architecture — corrected terminology

**Merlin** is the AI development/operations worker. **Artex** is an LLM cybersecurity framework, not an agent. **Titan** is an encryption scheme, not an agent. ChatGPT is the intended conversational front end.

## Authentication vs encryption
Titan may protect stored data only after its exact source, implementation, threat model, key lifecycle and independent cryptographic validation are established. Encryption alone cannot authenticate a user or authorize a business action. Use verified sessions (e.g., standards-based OAuth/OIDC), server-side authorization and managed keys; avoid repeated sign-ins through short-lived, securely refreshed sessions. Never expose long-lived secrets to Merlin.

## Continuous improvement and threat monitoring
- Start with passive, typed, payload-free events for rejected tool calls, provenance violations, integrity errors and authentication failures.
- Evaluate actual Artex framework against bounded synthetic prompt-injection and exfiltration fixtures. The existing security monitor is **not Artex**.
- Merlin can propose and test improvements on isolated branches, with independent evaluation, regression tests, rollback and human approval before promotion.
- No autonomous live exploitation, external target scanning, credential rotation, security-control bypass or unsupervised production deployment.
- Fail closed when Artex verification or identity service is unavailable.
- Alert staff on consequential findings. Never copy real customer data into research, prompts, or test fixtures.

## Release prerequisites
1. Recover and verify exact Artex and Titan source versions and security claims.
2. Implement identity-aware server-side policy and production/demo isolation.
3. Deploy authenticated HTTPS connector and test real ChatGPT request on synthetic data.
4. Independently verify security monitoring, logging privacy, encryption and recovery.
5. Pilot with approved real business records only after explicit security and privacy review.

The `security_monitor.py` module is a demonstration-only event counter. It does not perform threat hunting or continuous background execution.
