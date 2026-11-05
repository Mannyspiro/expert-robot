# Titan: Post-Quantum Cryptography and Mathematical Structure Research

**Status:** Research specification, version 0.1.0  
**Owner system:** Merlin / Expert Robot  
**Verification authority:** CACE  
**Dispatch boundary:** Hermes  
**Execution workers:** Avrea and authorized local/OCI runners  
**Promotion rule:** Capability may improve; authority does not automatically expand.

## 1. Purpose and non-goals

Titan is a research namespace for evaluating post-quantum cryptographic constructions, hybrid key establishment, cryptographic agility, and mathematical structures that may generate useful research hypotheses.

The objective is strong, well-specified confidentiality, integrity, authenticity, interoperability, and long-term verifiability. Increasing nominal key-space size is not itself a security proof. Hiding a construction's mathematical meaning is not a substitute for a defined security model, sound implementation, or peer review.

Titan MUST NOT deploy a novel cipher, key combiner, KEM, signature scheme, or obfuscation construction merely because it is novel, has a large parameter space, or passes internal tests. Experimental constructions remain isolated from production key material and production protocols.

## 2. Standards baseline

The baseline is the current NIST PQC standards and associated guidance, rechecked at each release:

- **FIPS 203 / ML-KEM:** standardized post-quantum key encapsulation.
- **FIPS 204 / ML-DSA:** standardized post-quantum digital signatures.
- **FIPS 205 / SLH-DSA:** stateless hash-based digital signatures.
- **NIST SP 800-227:** recommendations for key-encapsulation mechanisms.
- **NIST CSWP 39upd1:** crypto-agility strategies and practices.
- **NIST IR 8547:** transition guidance; use the final publication, not an earlier draft.

The production profile MUST select parameter sets and implementation modules based on the applicable standard, deployment requirements, validation status, and current guidance. Titan records exact standard editions, implementation versions, parameter sets, and configuration identifiers.

A hybrid key-establishment experiment may combine a classical component with ML-KEM, but only through a reviewed, domain-separated combiner and a fully specified protocol transcript. Do not assume that concatenating secrets or adding algorithms automatically creates a secure hybrid. Analyze downgrade behavior, transcript binding, authentication, failure handling, and interoperability. Hybrid composition is evaluated case by case.

For symmetric protection, use a well-reviewed AEAD construction from an approved implementation, with unique nonces and explicit key/nonce lifecycle rules. Use a standard KDF with domain separation. Do not invent a new AEAD or KDF in Titan's production profile.

## 3. Ideonomy catalogue

Represent each candidate as a typed, versioned record. Enumeration is for research coverage and hypothesis generation, not blind combinatorial deployment.

### Dimensions

1. **Security objective:** confidentiality, integrity, authenticity, forward secrecy, post-compromise recovery, key confirmation, archival verifiability.
2. **Adversary model:** classical, quantum, adaptive chosen-ciphertext, active network, compromised endpoint, malicious insider, supply-chain compromise.
3. **Primitive family:** lattice KEM, code-based KEM, hash-based signature, lattice signature, classical transition component, AEAD, KDF, randomness source.
4. **Mathematical lens:** algebraic structures, module/ring lattices, geometry of numbers, coding theory, combinatorics, probability, entropy, information theory, complexity, graph theory, representation theory, topology, dynamical systems.
5. **Composition:** key schedule, KDF/combiner, transcript binding, domain separation, authentication, version negotiation, rotation.
6. **Implementation:** constant-time behavior, memory handling, RNG, side-channel exposure, fault handling, language/runtime, hardware boundary.
7. **Evidence:** standard conformance, test vectors, independent implementation, formal model, proof assumptions, benchmark, external review.
8. **Lifecycle:** key generation, distribution, storage, backup, rotation, revocation, migration, destruction, recovery.

### Candidate record

Each candidate MUST include:
- stable `candidate_id` and schema version;
- parent hypothesis and provenance;
- objective and explicit threat model;
- primitive identifiers and exact standard/version references;
- mathematical representation and assumptions;
- protocol/composition description;
- claimed properties and properties explicitly not claimed;
- known limitations and unresolved questions;
- reproducible experiment plan;
- resource budget and stop conditions;
- evidence references and independent review state;
- promotion state: `idea`, `formalized`, `experimental`, `review_required`, `rejected`, or `qualified`.

Deduplicate by normalized construction identity and provenance, not by display name. Preserve rejected candidates and their reasons so the search does not repeatedly rediscover them.

## 4. Research programme and ranked work

### T0 — Standards and implementation inventory
Build a machine-readable inventory of FIPS 203/204/205, SP 800-227, crypto-agility guidance, available vetted library implementations, validation claims, parameter sets, and dependency versions. Distinguish standards conformance from formal validation and from a local test pass.

### T1 — Reference baseline
Create an isolated reference harness around established implementations. Test known-answer vectors, serialization boundaries, malformed inputs, key lifecycle behavior, interoperability, and deterministic reproducibility where the standard permits it. Never place production secrets in research fixtures.

### T2 — Hybrid composition study
Compare only documented/reviewable hybrid profiles. Record the component assumptions, combiner/KDF, domain separation, transcript binding, downgrade resistance, authentication, error behavior, and failure modes. Do not promote a custom combiner based on benchmark results alone.

### T3 — Mathematical ideonomy
Enumerate the mathematical lenses above and generate falsifiable hypotheses. Evaluate whether a lens contributes a theorem, a reduction, a useful invariant, a better implementation analysis, or merely an analogy. In particular:
- lattice geometry and module structure connect to ML-KEM analysis;
- coding theory provides an independent family of post-quantum assumptions;
- information theory and entropy quantify uncertainty but do not alone establish computational security;
- graph and category representations may improve protocol composition and provenance models;
- representation theory, n-ality, topology, and dynamical systems may inspire formal questions, but analogies are not cryptographic assumptions;
- UQFT/QFT, time-crystal and xenomathematical ideas remain separate exploratory tracks unless a precise, reviewable connection is demonstrated.

### T4 — Formal and independent verification
Model protocol state transitions and invariants. Use Lean for precisely stated lemmas and conditional theorems, with all assumptions and axiom dependencies recorded. A Lean proof of a model does not prove that production code implements that model; connect the formal artifact to source/build hashes and implementation tests.

### T5 — Independent review and promotion
Require review by qualified cryptographers independent of the candidate author. A candidate is not production-qualified solely because CACE verifies its hashes, tests pass, or a theorem compiles. Production adoption additionally requires standards compatibility, implementation review, operational key management, interoperability, and explicit human approval.

## 5. Experiment contract

Every run is immutable and reproducible. Record:
- experiment ID, candidate ID, schema version;
- source repository, exact Git commit SHA, dirty-tree status;
- dependency lockfile and toolchain versions;
- runner identity, OS/architecture, container or executable digest;
- exact command, declared inputs, input digests, output digests;
- deterministic seed only for non-secret test data;
- resource limits, start/end timestamps, exit status;
- test-vector and benchmark results;
- logs and artifact references;
- CACE verification result and verifier version;
- limitations, warnings, and reviewer status.

No secret key, private seed, credential, or sensitive plaintext may be placed in logs, receipts, or public artifacts. Use synthetic test material.

## 6. Bridge receipt profile

Define a versioned, signed attestation envelope. A receipt is valid only when the signature verifies against an authorized signer identity and all bindings match the actual execution.

Required signed fields:
- `receipt_version`;
- unique `receipt_id` and issuance time;
- signer key ID, signer identity, algorithm, and trust-chain/key-registration reference;
- repository URI, exact commit SHA, and working-tree state;
- artifact names, media types, and cryptographic digests;
- execution tool/worker identity, tool version, executable or image digest;
- declared command, input digests, output digests, and exit status;
- experiment/run ID and policy/resource profile;
- CACE verifier identity/version, verification result, and evidence references;
- explicit statement of what was and was not verified.

Canonicalize the payload before signing (use a documented deterministic encoding such as deterministic CBOR). Sign the canonical payload with an authorized key; include the signature algorithm and key identifier in the protected envelope. ML-DSA is a post-quantum signature option for a PQ-ready profile, subject to implementation and key-custody review. Do not claim a receipt is signed until a real execution result exists and an authorized signer has produced and independently verified the signature.

CACE MUST reject receipts with missing bindings, unknown or revoked signers, mismatched commit/artifact/tool digests, invalid signatures, unsupported schema versions, or unverifiable evidence. A receipt authenticates an attestation; it does not make the underlying cryptographic claim true.

## 7. Merlin integration contracts

- **Merlin registry:** canonical candidate, experiment, artifact, and review records; append-only provenance.
- **Hermes:** dispatches only an approved, versioned experiment contract; enforces idempotency, leases, timeout, and resource limits.
- **Avrea/OCI/local worker:** executes the declared job in an isolated environment and returns raw results plus artifact digests.
- **CACE:** independently verifies hashes, signatures, test evidence, formal artifacts, and declared policy; never trusts caller-supplied success flags.
- **Research dashboard:** read-only views over canonical registry and event data; clearly distinguishes demo, connected-idle, live, stale, and disconnected states.
- **Promotion gate:** no research result changes production configuration or authority without explicit approval and recorded review.

The first end-to-end acceptance test is one synthetic, non-secret experiment: register candidate -> dispatch through Hermes -> execute on an authorized worker -> collect artifacts -> verify independently with CACE -> issue an authorized signed receipt -> retrieve the same record from the canonical registry and dashboard.

## 8. Acceptance criteria

Titan foundation is complete only when:
1. schemas are versioned and validated;
2. catalogue entries are deduplicated and provenance-preserving;
3. the standards inventory includes source and edition dates;
4. baseline test vectors run reproducibly;
5. hybrid studies state assumptions and do not imply unproven composition security;
6. experiments are isolated from production secrets and configurations;
7. receipts bind signer, commit, artifact, tool, inputs, outputs, and verifier;
8. CACE independently rejects tampered or mismatched evidence;
9. dashboard status is derived from canonical state and freshness;
10. promotion requires independent review and explicit approval.

## 9. Primary references

- NIST PQC standards overview: https://csrc.nist.gov/projects/post-quantum-cryptography
- FIPS 203 (ML-KEM): https://csrc.nist.gov/pubs/fips/203/final
- FIPS 204 (ML-DSA): https://csrc.nist.gov/pubs/fips/204/final
- FIPS 205 (SLH-DSA): https://csrc.nist.gov/pubs/fips/205/final
- NIST SP 800-227 (KEM recommendations): https://csrc.nist.gov/pubs/sp/800/227/final
- NIST PQC publications and migration guidance: https://csrc.nist.gov/projects/post-quantum-cryptography/publications
- NIST crypto-agility publication CSWP 39upd1: https://csrc.nist.gov/pubs/cswp/39/upd1/final

---
**Current status:** Specification only. No Titan cryptographic implementation, production deployment, cryptographic qualification, bridge execution, or signed receipt is claimed by this document.
