# Merlin research brief: glyph mathematics, hyperbolic maps and Titan security

Date: 2026-11-04
Status: hypothesis generation; no cryptographic primitive proposal is approved.

## Executive conclusion

A visually unfamiliar symbolic language can improve how Merlin represents and combines mathematical ideas, but glyphs do not create entropy or cryptographic hardness. An enormous key space does not compensate for weak key generation, biased distributions, algebraic structure, side channels, or a flawed protocol.

Titan should retain standardized cryptographic components and study candidate mathematics in an isolated research track. No custom hyperbolic, trigonometric, glyph, rotor, permutation, or graph-derived function should enter production key derivation or encryption without a public security reduction, extensive independent cryptanalysis, and formal protocol review.

## Track A — glyph mathematics

The new `merlin.glyph_math_lab` defines a small typed notation:
- ⟁ composition
- ⌁ iteration
- ⟡ duality (only after a pairing/dual-space definition)
- ⧖ invariant (with proof obligation)
- ⫷ mapping
- ⟲ orbit
- ⋈ typed combination
- ⧉ domain/boundary

Every expression must declare domain and codomain. Composition checks type compatibility; iteration has an explicit non-negative bound; invariants require proof obligations. The grammar is deterministic and content-addressable. The symbols are a notation layer, not cryptographic material.

Research questions:
1. Can glyph notation encode category-theoretic composition, group actions, graph morphisms and geometric transformations without ambiguity?
2. Can Merlin translate glyph expressions into Lean definitions and proof obligations?
3. Can Ideonomy combine expressions only when types and assumptions unify?
4. Can CACE check that a generated theorem refers to the exact canonical expression bytes?

## Track B — hyperbolic mathematics

Study sinh, cosh, tanh, inverse hyperbolic functions, Möbius transformations, geodesic coordinates and hyperbolic geometry as mathematical objects. Evaluate:
- domain/range and branch behavior;
- injectivity, surjectivity and inverse definitions;
- numerical conditioning and precision loss;
- algebraic identities and symmetries;
- whether a proposed discrete construction reduces to a known problem.

A real-valued function such as tanh is not one-way merely because it is nonlinear. Its inverse is explicit on (-1,1): artanh(y) = 1/2 ln((1+y)/(1-y)). Floating-point saturation is a numerical artifact, not cryptographic hardness. Likewise, a smooth map on a continuous domain does not automatically yield a hard discrete inversion problem.

## Track C — Titan security foundations

Use published primitives and documented assumptions:
- ML-KEM (FIPS 203) for post-quantum key establishment, with current errata and NIST SP 800-227 reviewed before implementation.
- ML-DSA (FIPS 204) or SLH-DSA (FIPS 205) for signatures where appropriate.
- HKDF-SHA-256 for domain-separated key derivation.
- AES-256-GCM-SIV for authenticated encryption in the existing Titan research profile, subject to implementation and protocol review.

NIST FIPS 203 describes ML-KEM's security in relation to Module Learning With Errors (MLWE), and specifies ML-KEM-512, -768 and -1024. NIST SP 800-227 provides KEM recommendations. NIST notes a FIPS 203 issue for future correction; track the official errata before claiming conformance.

Do not invent a hybrid combiner. If hybrid key establishment is studied, use a published, specified construction and preserve its exact transcript and domain-separation rules.

## Track D — key-space analysis

For a uniformly sampled n-bit secret, the nominal search space is 2^n. This number is meaningful only if:
- the random generator has the required entropy;
- sampling is unbiased;
- secrets are generated and stored safely;
- the construction's security proof/assumption supports the claimed strength;
- protocol and implementation do not leak information.

Adding glyphs, rotor states or hyperbolic parameters can enlarge a representation without increasing effective security. Merlin should report effective security only from reviewed constructions and sound assumptions, not from raw combinatorial counts.

## Track E — research workflow improvements

1. Ideonomy creates typed hypotheses with explicit assumptions and falsifiers.
2. Hermes emits a deterministic research bundle and records the exact bytes.
3. Registry stores immutable artifacts and their SHA-256 identities.
4. CACE independently verifies source identity, artifact identity, schema and proof receipts.
5. Lean checks formal statements and assumptions; it does not certify cryptographic security by itself.
6. Research results remain `unreviewed` until independent review and human approval.

## Promotion gate

No custom cryptographic algorithm, hyperbolic one-way function, glyph cipher, rotor design or graph-derived key mechanism is eligible for Titan production. Research can proceed as pure mathematics, simulation, formalization and literature comparison. The trusted cryptographic boundary remains standardized and independently reviewed.
