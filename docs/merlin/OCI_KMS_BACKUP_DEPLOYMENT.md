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


## OCI Object Storage transport

The create-only transport uses the same instance-principal pattern but creates a dedicated Object Storage client for UploadManager and a separate client for HEAD/GET. This separation is intentional: OCI documents that UploadManager may modify timeout settings on its client, so it must not share a client used by unrelated operations. Multipart upload uses `if_none_match="*"`, SHA-256 request checksums, and metadata binding the object to the encrypted-envelope digest and size.

Set these additional non-secret protected runner values:

- `MERLIN_BACKUP_OCI_NAMESPACE`: exact Object Storage namespace.
- `MERLIN_BACKUP_OCI_BUCKET`: pre-created private bucket.
- `MERLIN_BACKUP_OCI_PREFIX`: optional safe prefix; defaults to `merlin/backups`.

The transport writes content-addressed names under `sha256/<first-two-hex>/<full-digest>.mrb.enc`, refuses overwrite, and accepts an existing object only when its HEAD metadata, size and digest exactly match. Download requires the expected SHA-256, pins an object version when supplied (otherwise uses ETag `if_match`), streams to a temporary file, verifies the full encrypted-envelope digest/size, and publishes without overwrite. It has no bucket-create, object-delete, retention-rule, or pre-authenticated-request methods.

### Bucket and IAM preflight

Before enabling remote backups:

1. A separate bucket administrator creates the bucket as private, disables public access and pre-authenticated requests, enables versioning if required by the recovery policy, and configures a locked retention rule covering the backup retention period.
2. The backup runner's dynamic group is limited to the designated runner. Its policy is restricted to creating new objects and reading/inspecting those objects in this bucket; it must not have object deletion/overwrite, bucket administration, retention-rule administration, or namespace administration rights.
3. A separate administrator identity owns retention configuration and break-glass recovery. The runtime backup principal must not be able to shorten or remove retention.
4. The bucket's region, namespace, bucket name, prefix, retention rule ID/period, versioning status, and IAM policy revision are recorded in the approval receipt.
5. Verify the bucket's server-side encryption configuration separately. Client-side AES-GCM remains mandatory; server-side encryption is an additional storage-layer control.

### Live remote-backup qualification

On the designated OCI runner, after the KMS live round trip has passed:

1. Run `OciObjectStorageBackupTransport.from_environment()`.
2. Encrypt a non-production registry backup with the live OCI KMS provider.
3. Upload it and record object name, exact envelope SHA-256/size, ETag, version ID (if enabled), request IDs and status.
4. Retry the same upload; it must be accepted only as an exact metadata/digest replay and must not overwrite the object.
5. Download by exact object name/version with the expected digest; verify bytes match, decrypt, and run the complete registry restore verifier.
6. Inspect Object Storage and Vault audit events independently. Do not treat SDK success alone as proof of correct IAM or retention.
7. Restore on a separate host into an empty registry root and measure recovery time.

Object Storage upload/download and bucket retention are implemented as a tested adapter contract, not live tenancy qualification. Until the above run is complete, no off-host backup or disaster-recovery claim is permitted.


A create-only retry is not accepted on metadata alone: after a conditional-create 412, Merlin downloads the existing object version (or ETag-pinned current object) and hashes the full encrypted envelope before returning an idempotent replay receipt. Upload requests also provide the base64-encoded expected SHA-256 to Object Storage for server-side checksum validation. This protects against stale or substituted bytes whose custom metadata was copied or left unchanged.


## Canonical recovery-drill receipt

Merlin now defines `merlin-backup-recovery-receipt/1` as an integrity-only record for a future live restore drill. It binds:
- source repository and full source commit, plus the exact workflow ID, run ID/attempt, matching source head, retained artifact ID/digest, and full Merlin ArtifactRef for the evidence bundle;
- separate Vault and Object Storage audit-export digests included in the retrievable evidence bundle;
- original backup package and manifest digests, plus the restored manifest digest (which must match);
- encrypted envelope SHA-256 and byte length;
- Object Storage namespace, bucket, content-addressed object name, ETag and optional version ID;
- KMS key OCID and opaque key-version identity (recorded from the provider/audit evidence, not inferred from an ordinal);
- restore host identity digest, protected runner profile, start/end timestamps and measured duration;
- explicit success checks for envelope authentication, archive verification, database integrity, foreign keys, blob inventory, ArtifactRef resolution, DAG history, Hermes outbox pointers and separate-host execution;
- restored inventory counts for blobs, ArtifactRefs, DAG snapshots and outbox events.

The receipt is canonicalized and SHA-256-bound, but intentionally unsigned. A successful local receipt digest is not CACE verification and does not qualify backup or recovery authority. CACE must independently attest the exact receipt bytes and bind the corresponding backup ArtifactRef before the result can enter a qualification DAG. Failed or missing checks are rejected, and a restored manifest mismatch cannot be represented as a successful drill.

This schema is a preparation contract only. No live OCI restore, separate-host drill, CACE attestation or recovery-time objective is claimed.
