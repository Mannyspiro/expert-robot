# Titan protocol model and reproducible vectors v1

## Purpose

This package defines a deterministic, versioned protocol-state model and canonical
structural test vectors for Titan's context-bound cryptographic envelope. It is
not a cryptographic implementation and does not generate ciphertext.

## Production boundary

The current research profile names HKDF-SHA-256 and AES-256-GCM-SIV. ML-KEM-768
is an optional research profile identifier, not an implemented KEM. No custom
hybrid combiner is specified. Any hybrid profile requires a published,
conformant construction and independent review.

The envelope structure requires version, suite, non-empty context, recipient key
identity, nonce, ciphertext and tag fields. The implementation consuming this
specification must canonicalize and authenticate the agreed metadata as
associated data, and must not release plaintext before authentication succeeds.

## Abstract state machine

initialized -> key_established -> keys_derived -> sealed -> authenticated -> accepted

Every stage has a fail-closed transition to rejected. The model describes
sequencing and acceptance conditions; it does not execute or prove the
cryptographic operations represented by those stages.

## Lean formalization

The module formal/MathAI/TitanProtocol.lean defines the abstract transition relation,
proves rejected and accepted states terminal, rules out a direct initialization-to-
acceptance transition, and states the logical preconditions for eligibility. These
theorems concern the specification only; they do not verify an implementation or
cryptographic primitive. The Lean module is imported by formal/MathAI.lean.

## Reproducible vectors

generate_structural_test_vectors() emits deterministic JSON fixtures for:
- valid envelope structure;
- missing context;
- unapproved suite;
- experimental-field contamination;
- unsupported envelope version.

Canonical bytes are UTF-8 JSON with sorted keys, compact separators, no NaN
values, and one terminal LF. SHA-256 digests identify exact model and vector
bytes. The test fixtures use opaque placeholder values for nonce, ciphertext
and tag; they are not cryptographic known-answer vectors and are not decryptable.

Primitive-level KDF, AEAD and KEM test vectors must be sourced from published
standards or independently validated implementations. Do not infer security
from these structural tests.

## Experimental boundary

Rotor selection, Steckerbrett permutations, changing lattices, graph mutation,
and Ko-memory path dependence remain isolated research hypotheses. They must
not influence production keys, KDF inputs, nonces, authenticated metadata,
ciphertext, or suite negotiation.

## Hermes -> registry/graph -> CACE

A Hermes research executor emits the canonical bundle bytes. The standard
build_hermes_stage_handlers() flow records those exact bytes using
ResearchEvidenceRecorder, verifies the registry artifact digest, links the
artifact to the hypothesis graph, and calls the injected CACE artifact verifier
with the same digest, repository commit, artifact kind/schema and logical path.
The returned Hermes result contains the artifact identity and CACE receipt
reference. Registry hashing establishes byte identity, not truth. CACE's
independent receipt must state the exact scope it checked.

No handler grants promotion authority. A human approval and separate review
remain required before any production adoption.
