# XMG-1D: Lean laws for Glyph Foundry

**Status:** Lean source committed; compilation has not yet been confirmed in the repository's configured Lean environment.

The module formalizes:
- left and right identity for typed function composition;
- associativity of composition;
- first and second projections of paired functions;
- integer double negation;
- invariance of integer natural absolute value under negation.

These are mathematical laws, not verification of the Python runtime. The integration milestone is to export rewrite-rule identifiers and proof artifact hashes from Lean, then require CACE to validate them against the exact rule definition and compiler/dependency versions.

The repository already contains Mathlib-based formal work under formal/MathAI. This module follows that import convention. The repository root did not expose lean-toolchain or lakefile.lean at the inspected paths, so the precise toolchain configuration still needs locating before compilation.
