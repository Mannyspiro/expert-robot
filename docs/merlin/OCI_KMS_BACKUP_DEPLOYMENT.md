# Merlin encrypted backup deployment runbook

Status: implementation and SDK contract tested; live OCI tenancy qualification NOT completed.

## Required protected configuration

Install the pinned optional OCI SDK dependency from `requirements-oci-kms.txt` on the designated OCI runner.

Set these non-secret values through the protected runner/deployment configuration:

- `MERLIN_BACKUP_KMS_KEY_OCID`: OCID of one customer-managed symmetric AES key.
- `MERLIN_BACKUP_KMS_CRYPTO_ENDPOINT`: exact Vault crypto endpoint returned for that Vault/key region.

Do not put private API keys, auth tokens, PEM private keys, or plaintext DEKs in these variables. The adapter uses `InstancePrincipalsSecurityTokenSigner`; it does not read a local OCI user profile.

## IAM and network preflight

Before enabling the capability, an OCI administrator must independently verify:

1. The dynamic group matches only the designated backup runner instance (not every instance in the compartment).
2. The instance principal has only the permissions needed to call GenerateDataEncryptionKey and Decrypt against the configured key. It must not receive key/vault administration, key creation, rotation, deletion, or secret-management rights.
3. The key is a customer-managed symmetric AES key suitable for AES-256 data-key generation.
4. The runner can reach the configured regional Vault crypto endpoint over TLS.
5. The key OCID, endpoint, compartment, region and instance OCID are recorded in the deployment approval/evidence record.

Do not infer an IAM policy is correct from a successful SDK construction. Confirm the actual policy scope and the OCI audit events for both operations.

## Live qualification sequence

On the designated runner, with protected configuration present:

1. Construct `OciKmsDataKeyProvider.from_environment()`; missing key OCID or endpoint must fail closed.
2. Call `generate_data_key()`; assert the returned plaintext key is exactly 32 bytes and the wrapped key is non-empty.
3. Call `unwrap_data_key(key_id, wrapped_key)`; compare the result in memory to the generated key. Never print either key.
4. Encrypt a non-production test backup with `MerlinBackupEncryption.encrypt`.
5. Decrypt it with the same provider; require envelope authentication, plaintext digest/size, and `MerlinRegistryBackup.verify_archive` to pass.
6. Capture only redacted operation metadata: key OCID, endpoint/region, instance identity, operation names, OCI request IDs, timestamps, status, encrypted-envelope digest, and backup manifest digest. Do not capture key material or wrapped-key payloads.
7. Verify the OCI audit trail independently and retain the test receipt with the backup package digest.

## Rotation and recovery

- Retain the original KMS key version for at least the retention period of every backup encrypted under it. OCI's wrapped data-key ciphertext is bound to the key version used at generation; test decryption after any rotation before disabling old versions.
- A key disable/delete action must be blocked while retained backups still depend on that key version.
- Restore must occur on a separate host into an empty registry root, then verify database integrity, all blob hashes, ArtifactRefs, DAG snapshots, and outbox pointers.
- A successful local decrypt test does not prove off-host delivery or retention. Object Storage upload/download, retention lock, independent backup signing, and disaster-recovery timing are separate qualification gates.

## Authority boundary

The KMS provider protects backup confidentiality and integrity. It does not attest artifact source truth, validate CACE signatures, qualify Lean proofs, or authorize production promotion. CACE must independently verify any signed backup/restore evidence before it can be used as a qualification input.
