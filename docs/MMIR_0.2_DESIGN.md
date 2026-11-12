# MMIR 0.2 — Typed Frames, N-ary Semantics, and Harmonic Models

Status: design contract; implementation and qualification are pending.

This document extends MMIR 0.1 without changing its core rule: a glyph is notation, never the source of operator semantics. Every expression must resolve to stable operator IDs, explicit types, and reproducible evaluation rules.

## 1. Scope and non-goals

MMIR 0.2 specifies homogeneous and heterogeneous N-ary operator applications; explicit precedence and associativity in parsed expressions; typed coordinate frames and transformations; harmonic/oscillator models with explicit physical parameters; and evidence-bearing numerical experiments.

It does not claim new physics, prove a conjecture, or make a glyph system intrinsically more expressive than conventional mathematics. Novel notation must be translated to a canonical expression graph and compared against a conventional baseline.

## 2. Operator contract

An operator definition has a stable operator_id and semantic namespace; namespace-scoped display glyphs; min_arity, max_arity, and an input signature; output type and semantic definition; declared algebraic laws marked assumed, conjectured, or proven; evaluation strategy and domain restrictions; version and content digest.

A one-element input signature means homogeneous operands. A positional signature must define every accepted operand position. Arity validation happens before evaluation. No law is inferred from glyph shape or name.

A rewrite rule is executable only when its preconditions are machine-checkable. A rule requiring associativity, commutativity, distributivity, or an identity must cite the law's evidence state. Conjectural laws may guide search but cannot silently rewrite a verified expression.

## 3. Parsing and evaluation order

The parser must preserve both source notation and the canonical expression graph. Precedence is explicit data, not hard-coded assumptions about glyphs. Each parser profile defines tokenization and escaping; prefix, infix, postfix, or mixfix fixity; precedence level; associativity (left, right, or non-associative); arity and namespace resolution; and ambiguity policy.

Ambiguous input is rejected or returned with multiple parse candidates; it is never resolved by an undocumented default. Round-trip tests must verify that parse -> render -> parse preserves the canonical graph and source spans.

## 4. Typed coordinate frames

A coordinate frame is a named basis plus dimension and quantity kind; unit for each axis; origin and orientation; handedness; frame identity and version.

A transform records source frame, target frame, transform kind, parameters, composition order, and validity domain. Initial supported transforms should be explicitly limited to affine maps with validated dimensions. Rotation, translation, scaling, and basis change must not be conflated.

A transform is not a physical law. Coordinate changes preserve represented quantities only when the transform's assumptions and units are satisfied. Frame mismatch, singular transforms where inversion is requested, and non-finite parameters must fail closed.

## 5. Harmonic model contract

The first numerical model is a classical damped oscillator:

    m x''(t) + c x'(t) + k x(t) = F(t)

where mass m, damping c, stiffness k, displacement x, and forcing F carry dimensionally compatible units. For an unforced underdamped oscillator, omega_0 = sqrt(k/m), gamma = c/(2m), and omega_d = sqrt(omega_0^2 - gamma^2).

A model record must include model ID and equation version; parameter values, units, and uncertainty if known; initial conditions and time domain; forcing function or an explicit unforced declaration; damping regime and boundary conditions; solver, solver version, step/tolerance policy; numeric precision, seed where applicable, and environment; output digest and residual/error summary.

The engine must check dimensions before solving. It must reject invalid parameter domains (for example m <= 0, k < 0 for this oscillator contract, or non-finite values). Critically damped and overdamped regimes must be represented explicitly rather than forcing a real-valued damped-frequency formula outside its domain.

## 6. Energy and resonance boundaries

For the unforced linear oscillator, mechanical energy is E = 1/2 m (x')^2 + 1/2 k x^2. For c >= 0, expected energy behavior is non-increasing; for c = 0 it is conserved up to numerical error. These become numerical regression properties, not proof claims about arbitrary systems.

Resonance is defined relative to a specified forcing model and frequency response, not as a universal assertion that every system maximizes amplitude at its undamped natural frequency. Report the model, damping, forcing, and measurement criterion whenever resonance is discussed.

The words energy, vibration, and frequency must retain their established physical meanings. Metaphorical or speculative extensions are tagged as such and kept separate from dimensional physical calculations.

## 7. Evidence and qualification

Each numerical run emits a receipt containing exact source/model digest and parameter digest; solver and dependency versions; precision, tolerances, seed, and execution environment; termination state, runtime, and resource use; output digest, residuals, and validation checks.

A successful numerical run is not a formal proof. Formal claims require Lean source, pinned toolchain/dependencies, compiler result, and independent CACE verification bound to the exact artifact digest. Missing or ambiguous evidence remains unqualified.

## 8. Required test matrix

1. Homogeneous N-ary operators at minimum, interior, and maximum arity.
2. Heterogeneous positional signatures and rejection of incomplete signatures.
3. Namespace collisions and ambiguous parser input.
4. Precedence/associativity parse fixtures and lossless round trips.
5. Coordinate frame mismatch, unit mismatch, singular inverse, and finite-value guardrails.
6. Transform composition order and identity/inverse properties where declared.
7. Oscillator dimensional consistency and invalid parameter rejection.
8. Underdamped, critically damped, and overdamped analytic fixtures.
9. Undamped energy conservation and damped non-increasing energy within declared numerical tolerances.
10. Deterministic replay and receipt digest stability.
11. Negative tests proving conjectural laws cannot be used as proven rewrites.
12. CACE receipt verification against the exact source and output digests.

## 9. Implementation sequence

- 0.2a: extend type system with quantity kinds and typed frame identifiers.
- 0.2b: parser profile and precedence metadata; canonical AST round-trip tests.
- 0.2c: frame and transform value types with checked composition.
- 0.2d: oscillator model validation and deterministic numerical adapter.
- 0.2e: evidence receipt schema and independent CACE verification.
- 0.2f: held-out comparison against conventional notation and baseline solvers.

Do not merge or mark qualified based on compilation alone. Keep each increment small, testable, and independently reviewable.

## 0.2 implementation gate: runner availability

The MMIR branch's CI workflow currently targets the custom runner label
`avrea-ubuntu-latest-8-vcpu`. The GitHub Actions job metadata for the latest
run (run `43143807743`, job `130936813986`) reports:

- job status: cancelled;
- job conclusion: cancelled;
- runner name and runner group: empty;
- labels requested: `avrea-ubuntu-latest-8-vcpu`;
- no steps were created and no job logs are available.

This is evidence that the job did not reach a recorded runner/step execution.
It does not establish whether the runner is offline, a queue/dispatch service
cancelled the job, or another external cancellation occurred. The workflow
concurrency policy was changed to queue rather than cancel in-flight runs, but
the subsequent run still ended before any step. Do not treat this as a C++
build or MMIR test failure, and do not claim a passing build.

**Release gate:** restore/verify dispatch for the requested Avrea runner label,
then require a completed configure, build, and CTest run before promoting the
MMIR implementation. Until then, code changes should remain small and their
verification status explicitly marked pending.

## 0.2a source audit: implementation boundary

A source review of the current MMIR 0.1 implementation confirms that the
following are present: seven SI base-dimension exponents; positive finite unit
scales; dimensional multiplication/division/integer powers; compatible-unit
conversion; namespace-scoped glyph lookup; typed operator signatures; graph
operand/type/arity checks; and rejection of implicit dependency cycles.

The following 0.2 contract items are **not implemented yet**:

- Quantity kinds are not distinct from SI dimension vectors. Two quantities
  with identical dimensions but different semantic kinds (for example,
  frequency versus radioactive activity) currently compare as dimensionally
  compatible.
- NodeKind coordinate_frame and transformation are labels only; there are no
  frame value objects, transform matrices, composition rules, inverse checks,
  or frame-identity validation.
- Algebraic-law booleans in OperatorSpec are declarations, not evidence.
  There is no per-law state/evidence object or rewrite engine enforcing
  assumed/conjectured/proven distinctions.
- There is no parser profile, precedence table, fixity model, source-span
  preservation, or parse/render round-trip implementation.
- The harmonic node kind has no oscillator model, numerical solver, or
  reproducible run receipt.

### Corrective implementation order

1. Add QuantityKind and TypedQuantity semantics without changing the
   existing SI exponent representation; reject operations whose quantity-kind
   rules are undefined even when dimensions happen to match.
2. Replace free-standing algebraic-law booleans with law declarations carrying
   an explicit evidence state and evidence reference. Do not permit a rewrite
   based only on a glyph, name, or self-asserted boolean.
3. Implement typed frame identities and affine transform composition with
   explicit source/target frames, dimension checks, finite-value checks, and
   singular-inverse rejection.
4. Add parser profiles only after the canonical operator and type contracts
   stabilize.
5. Add the oscillator solver and numerical receipts after dimensional and
   frame validation can be reused.

These are source-level findings, not test results. The runner gate above still
blocks compilation and execution qualification; no 0.2 implementation item
should be described as passing until a real build/test receipt exists.
