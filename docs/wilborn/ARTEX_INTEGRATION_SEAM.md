# Artex LLM security framework — integration seam

The code in `wilborn_ops/llm_boundary.py` is a **test-only, fail-closed tool dispatcher**, not the actual Artex framework. The `artex_verified` boolean is caller-supplied and therefore **not a trustworthy security attestation**. Never expose this dispatcher to untrusted users, LLM-generated code or the network. Its purpose is to freeze allowlisted tool contracts and demonstrate negative tests until the real Artex framework and trusted verifier are identified.

## Actual production integration requirements
1. Locate authoritative Artex source, version and documented LLM security controls.
2. Integrate its checks behind a trusted server-side verification adapter that cannot be bypassed by callers.
3. Independently test prompt-injection, tool injection, data exfiltration and approval-bypass attempts using synthetic fixtures.
4. Enforce identity and per-record access in the protected backend even when Artex passes a request.
5. Keep Titan separate as a cryptographic scheme. Identify and qualify Titan before any real customer data use.
6. Do not allow AI or untrusted content to set `artex_verified=True` in production.

This milestone does not establish actual Artex coverage or production protection.
