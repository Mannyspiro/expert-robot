import copy
import unittest

from merlin.backup_recovery_receipt import (
    REQUIRED_CHECKS,
    build_backup_recovery_receipt,
    verify_backup_recovery_receipt,
)


class BackupRecoveryReceiptTests(unittest.TestCase):
    def setUp(self):
        envelope_digest = "a" * 64
        self.payload = {
            "schema": "merlin-backup-recovery-receipt/1",
            "source": {
                "repository": "Mannyspiro/expert-robot",
                "commit": "b" * 40,
            },
            "execution_evidence": {
                "repository": "Mannyspiro/expert-robot",
                "workflow_id": "registry-backup-restore.yml",
                "run_id": 123456,
                "run_attempt": 1,
                "head_sha": "b" * 40,
                "artifact_id": 654321,
                "artifact_sha256": "f" * 64,
                "artifact_ref": {
                    "schema": "merlin-artifact-ref/1",
                    "project_id": "merlin",
                    "logical_path": "recovery/drill/evidence.json",
                    "version": 2,
                    "sha256": "f" * 64,
                },
                "vault_audit_sha256": "1" * 64,
                "object_storage_audit_sha256": "2" * 64,
            },
            "backup": {
                "package_sha256": "c" * 64,
                "manifest_sha256": "d" * 64,
                "restored_manifest_sha256": "d" * 64,
            },
            "encrypted_envelope": {
                "sha256": envelope_digest,
                "size_bytes": 4096,
            },
            "object_storage": {
                "namespace": "example_namespace",
                "bucket": "merlin-backups",
                "object_name": f"merlin/backups/sha256/aa/{envelope_digest}.mrb.enc",
                "version_id": "version-7",
                "etag": "etag-7",
            },
            "kms": {
                "key_ocid": "ocid1.key.oc1..example",
                "key_version_id": "ocid1.keyversion.oc1..version3",
            },
            "restore": {
                "origin_host_identity_sha256": "9" * 64,
                "host_identity_sha256": "e" * 64,
                "runner_profile": "protected-oci-restore",
                "started_at_unix_ms": 1000,
                "completed_at_unix_ms": 9250,
                "duration_ms": 8250,
            },
            "checks": {name: True for name in REQUIRED_CHECKS},
            "counts": {
                "blob_count": 12,
                "artifact_ref_count": 19,
                "snapshot_count": 8,
                "outbox_event_count": 8,
            },
        }

    def test_valid_receipt_round_trips_as_integrity_only(self):
        receipt = build_backup_recovery_receipt(self.payload)
        result = verify_backup_recovery_receipt(receipt)
        self.assertTrue(result["verified"])
        self.assertEqual(result["authority"], "integrity-only")
        self.assertTrue(result["cace_attestation_required"])
        self.assertEqual(len(receipt["receipt_sha256"]), 64)

    def test_receipt_digest_detects_mutation(self):
        receipt = build_backup_recovery_receipt(self.payload)
        receipt["restore"]["runner_profile"] = "different-runner"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            verify_backup_recovery_receipt(receipt)

    def test_rejects_execution_artifact_ref_digest_mismatch(self):
        payload = copy.deepcopy(self.payload)
        payload["execution_evidence"]["artifact_ref"]["sha256"] = "9" * 64
        with self.assertRaisesRegex(ValueError, "ArtifactRef digest mismatch"):
            build_backup_recovery_receipt(payload)

    def test_rejects_execution_head_that_differs_from_source_commit(self):
        payload = copy.deepcopy(self.payload)
        payload["execution_evidence"]["head_sha"] = "8" * 40
        with self.assertRaisesRegex(ValueError, "does not match the source commit"):
            build_backup_recovery_receipt(payload)

    def test_rejects_restored_manifest_mismatch(self):
        payload = copy.deepcopy(self.payload)
        payload["backup"]["restored_manifest_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "does not match"):
            build_backup_recovery_receipt(payload)

    def test_rejects_object_name_not_bound_to_envelope_digest(self):
        payload = copy.deepcopy(self.payload)
        payload["object_storage"]["object_name"] = "merlin/backups/sha256/bb/" + "b" * 64 + ".mrb.enc"
        with self.assertRaisesRegex(ValueError, "not bound"):
            build_backup_recovery_receipt(payload)

    def test_rejects_failed_or_missing_restore_check(self):
        payload = copy.deepcopy(self.payload)
        payload["checks"]["separate_host"] = False
        with self.assertRaisesRegex(ValueError, "failed or missing"):
            build_backup_recovery_receipt(payload)

    def test_rejects_restore_on_the_same_host_as_backup_origin(self):
        payload = copy.deepcopy(self.payload)
        payload["restore"]["host_identity_sha256"] = payload["restore"]["origin_host_identity_sha256"]
        with self.assertRaisesRegex(ValueError, "must differ from backup origin"):
            build_backup_recovery_receipt(payload)

    def test_rejects_duration_that_does_not_match_timestamps(self):
        payload = copy.deepcopy(self.payload)
        payload["restore"]["duration_ms"] += 1
        with self.assertRaisesRegex(ValueError, "does not match timestamps"):
            build_backup_recovery_receipt(payload)

    def test_rejects_boolean_as_integer_count(self):
        payload = copy.deepcopy(self.payload)
        payload["counts"]["blob_count"] = True
        with self.assertRaisesRegex(ValueError, "integer"):
            build_backup_recovery_receipt(payload)

    def test_rejects_unknown_fields_and_missing_receipt_digest(self):
        payload = copy.deepcopy(self.payload)
        payload["untrusted_extra"] = "must not be silently retained"
        with self.assertRaisesRegex(ValueError, "invalid field set"):
            build_backup_recovery_receipt(payload)
        with self.assertRaisesRegex(ValueError, "digest is required"):
            verify_backup_recovery_receipt(self.payload)


if __name__ == "__main__":
    unittest.main()
