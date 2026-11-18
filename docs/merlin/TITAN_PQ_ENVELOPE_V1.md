# Titan bounded post-quantum envelope v1

This opt-in local adapter performs actual encryption through the maintained
`cryptography` HPKE implementation. It implements no cipher, KEM, key derivation,
nonce scheme or hybrid combiner. `age`, liboqs and pqcrypto were absent locally;
the installed high-level HPKE API avoids manually composing those primitives.

The tested profile is pinned to **cryptography 50.0.0**, whose bundled backend
reports **OpenSSL 4.0.1 (9 June 2026)**. The separate system OpenSSL CLI reports
3.5.7 and ML-KEM support; the adapter does not invoke that executable. A missing
or changed pinned Python/backend implementation blocks operation. Nothing is
downloaded, installed or silently replaced with classical encryption.

The current upstream patch release inspected during this acceptance is
**50.0.2**, whose release notes specify OpenSSL 4.0.3 wheels. That release is
not installed in this workspace and has not been executed here. The adapter
therefore rejects it under this narrowly pinned development profile rather than
claiming unmeasured patch compatibility. This local pin is not a recommendation
to downgrade or a deployment acceptance result: an approved current patch must
be retested before production use. See the
[upstream release notes](https://github.com/pyca/cryptography/blob/4dda5c7fe4ae71b8925f2551910a0ef959df9c7a/CHANGELOG.rst).

The sole suite is `HPKE-ML-KEM-768-HKDF-SHA256-AES-256-GCM`. It uses the library's
single-shot `Suite.encrypt()` / `Suite.decrypt()`. HPKE is described in
[RFC 9180](https://www.rfc-editor.org/rfc/rfc9180.html), an informational CFRG RFC;
that RFC does not itself specify this later ML-KEM extension or Titan's wrapper.
The [cryptography 50.0.0 HPKE documentation](https://cryptography.io/en/50.0.0/hazmat/primitives/hpke/)
specifies the implemented suite interface and application binding through
`info`. The [ML-KEM interface](https://cryptography.io/en/50.0.0/hazmat/primitives/asymmetric/mlkem/)
implements ML-KEM from [FIPS 203](https://csrc.nist.gov/pubs/fips/203/final).
These references are not an audit or qualification of this application profile.
The earlier Titan structural-model artifact names a different AEAD; it remains a
structural research fixture and is not silently substituted or used for crypto.

## Interface and authenticated framing

`generate_recipient_keypair()` returns `(public_key_bytes, private_seed_bytes)`:
1184 public bytes and a secret 64-byte seed. The caller owns key distribution,
trust, access control, rotation and storage; this module persists no key.

`encrypt(payload, public_key, public_context, pad_to=65536)` returns canonical
UTF-8 JSON envelope bytes. Public context contains only generic `purpose` and
`schema` labels. Extra fields, including board parameters or history digests,
are rejected. Actual board configuration, moves, Ko state and message bytes
belong inside the private encoded payload supplied by the board module.

The authenticated plaintext is an eight-byte big-endian content length, original
bytes and random padding to an explicitly selected bucket: 4096, 16384, 65536,
262144 or 1048576 bytes. The payload must fit the selected bucket minus eight;
the adapter never changes buckets automatically. Equal-bucket envelopes with
the same public labels have the same length regardless of private content or
move count. Fresh HPKE encapsulation changes ciphertext on repeated encryption.

The public header contains only wrapper schema/version, fixed suite, padding
bucket and generic context. Its canonical bytes and a non-transmitted recipient
public-key hash are bound in HPKE `info`. Ciphertext is the library's encapsulated
key plus AEAD ciphertext/tag in canonical base64. No plaintext digest, board
dimension, exact content length or recipient-key identifier is published.

`decrypt(envelope, private_seed, expected_context)` verifies the fixed suite,
version, canonical encoding, allowed bucket, exact expected context and bounded
ciphertext length before opening. No plaintext or internal length is returned
before HPKE authentication succeeds. Malformed input, wrong keys/context,
changed metadata and failed tags raise only `TitanDecryptionError("decryption failed")`.
Unavailable dependencies are a separate configuration error. Envelope parsing
is capped at 1,500,000 bytes; maximum payload is 1,048,568 bytes.

## Measured scope and limits

The focused test command is:

```sh
PYTHONPATH=python python -m unittest discover -s tests -p test_titan_pq_envelope.py -v
```

Eight local tests execute real ML-KEM encapsulation/decapsulation and HPKE,
including all padding boundaries, arbitrary-byte recovery, equal-bucket length,
fresh encryption, wrong key/context, changed encapsulation/tag/header, downgrade,
JSON type confusion and bounded malformed input. On hosts lacking this pinned
optional profile, the crypto tests explicitly skip; no substitute result counts
as encryption acceptance. The OCI core profile is not assumed to contain it.

Base-mode HPKE does not authenticate a sender: anyone holding the recipient's
public key can create an envelope. This is not a replay/order protocol, key
management system, archival recovery system or anonymity mechanism. Recipient
key compromise can expose recorded messages. Python does not guarantee secure
memory erasure. Public suite/context/bucket, message count, timing, endpoints and
traffic volume remain observable. Bucket padding does not establish that an
observer “gets nothing,” and no claim of general side-channel resistance follows.
No independent cryptographic review, production deployment or qualification is
claimed by passing these tests. No caller permissions or LMS mastery change.

## Published vector acceptance and explicit coverage gap

The additional `test_titan_pq_published_vectors.py` checks a public ML-KEM-768
recipient seed/public key and decapsulation shared secret against an upstream
known answer. It also decrypts the published **AES-128-GCM** HPKE vector using
the same test-only AAD entry point used by PyCA's own tests. The production
adapter uses only the public Suite API. The public vector seed is test material,
never a live key.

The vector is extracted without changing its values from
[PyCA 50.0.2](https://github.com/pyca/cryptography/blob/4dda5c7fe4ae71b8925f2551910a0ef959df9c7a/vectors/cryptography_vectors/HPKE/hpke-pq-test-vectors.json),
commit `4dda5c7fe4ae71b8925f2551910a0ef959df9c7a`, Git blob
`d8c9a715dc990fced620d66fd0bbcdb21ba66742`, full-file SHA-256
`ba1f90672903e0df25610a1eef84b5f157e44d34849c0a72a2f9b164f3213888`.
The corresponding
[HPKE working-group vectors](https://github.com/hpkewg/hpke-pq/blob/6433c8fce0b8b749dfc86c1095081a88698ccfab/test-vectors.json)
are pinned at `6433c8fce0b8b749dfc86c1095081a88698ccfab`, Git blob
`f63ea7c7e88fb6fc3742d46b2453371ef9661c61`, full-file SHA-256
`35c59f4a0132e5631e50ac039d8ca3a72e99f5e92dfd94d45338d6ae243f613c`.
Only a compact public extraction and suite inventory are stored as the fixture.

Both pinned files contain thirteen suite vectors. **Neither contains the exact
Titan v1 tuple** `(ML-KEM-768=65, HKDF-SHA256=1, AES-256-GCM=2)`.
The published ML-KEM-768/HKDF-SHA256 case uses AES-128-GCM=1. Component and
adjacent-suite acceptance must not be reported as an exact AES-256-GCM KAT.
The exact v1 suite currently has real library roundtrip/tamper/boundary tests,
with the external full-suite known-answer gap left open. No new primitive,
hand-written vector or downgrade was introduced to conceal that gap.

Local acceptance on November 18, 2026 passed all 35 `test_titan*.py` tests with
zero skips: eight real-envelope tests, three published-vector/provenance tests,
twelve board-record tests and twelve existing structural/registry tests. This
includes encrypting and recovering arbitrary message bytes together with three
19³ boards, full permutations, mirror cells and recorded history in a 262144-byte
padding bucket. The smaller October board record in the same bucket has the
same public header and ciphertext length. These public synthetic examples do
not establish an exact-suite external KAT, current-patch acceptance, anonymity,
or general cryptographic security.
