# MMIR 0.1 — Mathematical Intermediate Representation

Status: experimental specification and initial C++ validation substrate.

## Purpose

MMIR is the canonical typed representation for conventional mathematics and
Xeno-Math experiments. Glyphs are display aliases, not semantics. Every
application resolves to a stable operator ID with explicit arity, input types,
output type, namespace, and semantic definition.

## Core invariants

1. A glyph is resolved only inside a semantic namespace.
2. Every operator declares a minimum and maximum arity and typed inputs.
3. Applications must satisfy arity and input/output type constraints.
4. An expression dependency graph must be acyclic unless a future explicit
   feedback/recursion node defines the cycle semantics.
5. Operator laws (associativity, commutativity, identity, inverse,
   distributivity) are metadata, not assumptions inferred from a glyph.
6. A specified operator is not thereby formally proven or physically validated.
7. Units and SI dimensions are represented separately from display notation.

## Initial C++ substrate

- `OperatorRegistry`: stable operator IDs and namespace-scoped glyph lookup.
- `ExpressionGraph`: typed nodes and operand dependencies.
- `validate`: unknown operator, arity, input/output type, missing operand,
  and implicit-cycle checks.
- `MathType`: SI base-dimension exponents, display unit, and positive scale-to-SI factor.
- Dimensional algebra: multiplication, division, integer powers, dimension
  comparison, and safe conversion between compatible linear units.

## Next increments

- 0.1.1: dimensional inference and unit conversion contracts.
- 0.2: N-ary operators, typed coordinate frames, and explicit feedback nodes.
- 0.3: parser/renderer with lossless round-tripping.
- 0.4: harmonic models with explicit phase, frequency, amplitude, damping,
  coupling, and energy boundary conditions.
- 0.5: equality-saturation optimizer with proof-carrying rewrite rules.
- 1.0: Lean-backed formal contracts and independent CACE artifact receipts.

## Research discipline

New notation must beat a conventional baseline on measured comprehension,
error rate, expression depth, or proof/search cost without changing semantics.
All claims remain conjectural until formal or reproducible numerical evidence
supports them.


## 0.1.1 validation hardening

The registry rejects zero-arity operators in this initial application model,
malformed positional input signatures, and self-asserted verification labels.
A single declared input type means all operands share that type. A positional
signature must declare one type for every possible operand slot. Accepted
local statuses are `specified`, `conjectural`, and `unqualified`; formal or
numerical qualification must arrive through separate evidence records rather
than a registry string.


## Dimensional model boundaries

The current unit model supports multiplicative linear conversions only. It
does not model affine units such as degrees Celsius, logarithmic units such as
decibels, contextual currencies, or uncertainty intervals. Dimension vectors
use integer SI exponents in this increment; rational exponents are deferred.
Conversion rejects non-finite values, invalid scales, and incompatible
dimensions rather than guessing.
