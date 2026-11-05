# Merlin local mathematical-discovery integration

## What is now wired

- `math_discovery_backends.py` adapts the real `simulate_linear_ode` RK4 implementation.
- The RK4 adapter records the implementation version, Python runtime identity, request parameters, precision, seed, raw output digest and deterministic replay comparison.
- The finite cyclic-translation search exhaustively checks only caller-declared integer bounds. A completed bounded search is not a proof over all moduli.
- Ideonomy's round-robin bridge is deliberately narrow: only compatible simplices containing `event-queue` and `cpu-locality` can emit the cyclic-translation claim. Other simplex combinations remain unformalized proposals.
- The claim contains assumptions, a falsifiable finite-search criterion, exact formal statement, supplied Lean source, and source-identity metadata.
- The Lean adapter compiles that supplied source. The integrated executor no longer calls `lean_scaffold()` for eligible claims.
- Lean status `compiled_unverified` is retained as compilation evidence only. `proof_verified` remains false until an independent CACE theorem receipt verifies the exact target and source.
- The canonical Hermes handler stores exact artifact bytes through `ResearchEvidenceRecorder` before CACE is asked to verify their registry digest.
- Handler construction now refuses a missing or non-`CaceVerificationAdapter` verifier, and refuses an adapter whose `verify_transport` is unset.

## Local setup

From the repository root, install the project's declared Python dependencies and make the `python` directory importable (for example, use the project's existing editable-install or PYTHONPATH convention). The Lean compiler uses the pinned `formal/lean-toolchain` and Lake manifest.

Run the focused local tests:

```bash
pytest -q tests/test_math_discovery_backends.py
```

These tests exercise the real RK4 function, finite integer enumeration, the narrow Ideonomy claim factory and the CACE adapter's fail-closed behavior when no transport exists.

## Configure an actual CACE transport

Construct `CaceVerificationAdapter` with:
- the canonical `MerlinRegistry`,
- the durable `MerlinEventOutbox`,
- the canonical `MerlinKnowledgeGraph` when graph receipt edges are required,
- a real authenticated `verify_transport(request)` callable targeting an independently operated CACE verifier.

The transport must return a receipt conforming to the exact schema expected by `CaceVerificationAdapter`. For theorem receipts, it must bind repository, commit, exact artifact digest and theorem; authenticate the source commit; verify the artifact digest; identify an independent verifier; report kernel checking, exact target declaration and axiom audit; and include a canonical SHA-256 receipt digest. For non-theorem artifact receipts, it must bind the artifact kind/schema/path and report independent schema/content checks.

A local mock may test serialization and validation branches, but it is not CACE, must not use a production verifier identity, and must never be recorded as an independent proof result. The focused tests intentionally do not manufacture a successful CACE receipt.

## Hermes registration

Use `build_default_local_math_discovery_handlers(..., cace_adapter=real_adapter)` to register the actual local numerical and finite-search implementations with the existing research, numerical-experiment and proof-search stage contracts. The builder fails closed until the independent CACE transport exists. It does not grant promotion authority.

## Avrea boundary

No Avrea dispatch integration is configured by these changes. No Avrea worker action, compute allocation, or external job is claimed. Avrea remains a separately approved execution boundary; this local milestone uses the in-process RK4 and finite search implementations only.

## Evidence interpretation

- RK4 output is numerical evidence, not a proof.
- Exhaustive search is complete only over its recorded bounds.
- Lean compilation is not independent theorem verification.
- A registry hash proves byte identity, not mathematical truth.
- Only an authenticated independent CACE receipt can set an independently verified status.
- `promotion_authority` remains false throughout.
