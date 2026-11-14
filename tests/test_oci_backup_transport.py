import base64
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from merlin.backup_encryption import MAGIC, MerlinBackupEncryption
from merlin.oci_backup_transport import (
    OciObjectStorageBackupTransport,
    ObjectStorageConflict,
)
from merlin.project_registry import MerlinRegistry
from merlin.registry_backup import MerlinRegistryBackup


class FakeKeyProvider:
    def generate_data_key(self):
        return "test-key/v1", b"D" * 32, b"wrapped-dek"

    def unwrap_data_key(self, key_id, wrapped_key):
        if key_id != "test-key/v1" or wrapped_key != b"wrapped-dek":
            raise ValueError("bad test key envelope")
        return b"D" * 32


class FakeServiceError(Exception):
    def __init__(self, status):
        super().__init__(f"fake object storage status {status}")
        self.status = status


class FakeRawStream:
    def __init__(self, content):
        self.content = content

    def stream(self, chunk_size, decode_content=False):
        for start in range(0, len(self.content), chunk_size):
            yield self.content[start:start + chunk_size]


class FakeObjectStorageClient:
    def __init__(self):
        self.objects = {}

    def head_object(self, namespace, bucket, object_name, version_id=None):
        key = (namespace, bucket, object_name)
        if key not in self.objects:
            raise FakeServiceError(404)
        item = self.objects[key]
        if version_id and version_id != item["version_id"]:
            raise FakeServiceError(404)
        return SimpleNamespace(headers=dict(item["headers"]))

    def get_object(self, namespace, bucket, object_name, if_match=None, version_id=None):
        key = (namespace, bucket, object_name)
        if key not in self.objects:
            raise FakeServiceError(404)
        item = self.objects[key]
        if version_id and version_id != item["version_id"]:
            raise FakeServiceError(404)
        if if_match and if_match != item["headers"]["etag"]:
            raise FakeServiceError(412)
        return SimpleNamespace(data=SimpleNamespace(raw=FakeRawStream(item["data"])))


class FakeUploadManager:
    def __init__(self, client):
        self.client = client
        self.calls = []

    def upload_file(self, namespace, bucket, object_name, file_path, **kwargs):
        self.calls.append((namespace, bucket, object_name, dict(kwargs)))
        key = (namespace, bucket, object_name)
        if key in self.client.objects:
            raise FakeServiceError(412)
        data = Path(file_path).read_bytes()
        expected_sha256 = hashlib.sha256(data).digest()
        if kwargs.get("opc_content_sha256") != base64.b64encode(expected_sha256).decode("ascii"):
            raise AssertionError("upload did not bind the expected SHA-256 checksum")
        etag = hashlib.sha256(data).hexdigest()
        headers = {
            "content-length": str(len(data)),
            "etag": etag,
            "opc-version-id": "version-1",
        }
        for name, value in kwargs["metadata"].items():
            headers[f"opc-meta-{name}"] = value
        self.client.objects[key] = {
            "data": data,
            "headers": headers,
            "version_id": "version-1",
        }
        return SimpleNamespace(headers=headers)


class OciObjectStorageBackupTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "registry"
        registry = MerlinRegistry(self.root)
        registry.register_project("merlin", "Merlin")
        registry.put_artifact("merlin", "research/input.txt", b"backup transport fixture")
        self.backup = Path(self.temp.name) / "backup.zip"
        MerlinRegistryBackup(self.root).backup_to(self.backup)
        self.encrypted = Path(self.temp.name) / "backup.mrb.enc"
        self.encryption_receipt = MerlinBackupEncryption.encrypt(
            self.backup, self.encrypted, FakeKeyProvider(),
        )
        self.client = FakeObjectStorageClient()
        self.upload_manager = FakeUploadManager(self.client)
        self.transport = OciObjectStorageBackupTransport(
            "test-namespace", "merlin-backups",
            prefix="merlin/backups",
            read_client=self.client,
            upload_manager=self.upload_manager,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_upload_is_content_addressed_create_only_and_idempotent(self):
        first = self.transport.upload_encrypted_backup(
            self.encrypted, expected_sha256=self.encryption_receipt["envelope_sha256"],
        )
        replay = self.transport.upload_encrypted_backup(self.encrypted)
        self.assertEqual(first["object_name"], replay["object_name"])
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        self.assertEqual(first["version_id"], "version-1")
        kwargs = self.upload_manager.calls[0][3]
        self.assertEqual(kwargs["if_none_match"], "*")
        self.assertEqual(kwargs["opc_checksum_algorithm"], "SHA256")
        self.assertEqual(
            kwargs["metadata"]["merlin-sha256"],
            self.encryption_receipt["envelope_sha256"],
        )

    def test_download_pins_version_and_verifies_complete_envelope_bytes(self):
        uploaded = self.transport.upload_encrypted_backup(self.encrypted)
        destination = Path(self.temp.name) / "downloaded.enc"
        receipt = self.transport.download_encrypted_backup(
            uploaded["object_name"], destination,
            expected_sha256=uploaded["sha256"],
            expected_size=uploaded["size_bytes"],
            version_id=uploaded["version_id"],
        )
        self.assertEqual(destination.read_bytes(), self.encrypted.read_bytes())
        self.assertEqual(receipt["sha256"], uploaded["sha256"])
        self.assertEqual(receipt["version_id"], "version-1")

    def test_download_rejects_substituted_object_bytes(self):
        uploaded = self.transport.upload_encrypted_backup(self.encrypted)
        key = ("test-namespace", "merlin-backups", uploaded["object_name"])
        original = self.client.objects[key]["data"]
        self.client.objects[key]["data"] = b"x" * len(original)
        destination = Path(self.temp.name) / "substituted.enc"
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.transport.download_encrypted_backup(
                uploaded["object_name"], destination,
                expected_sha256=uploaded["sha256"],
            )
        self.assertFalse(destination.exists())


    def test_idempotent_replay_rejects_substituted_bytes_even_when_metadata_matches(self):
        uploaded = self.transport.upload_encrypted_backup(self.encrypted)
        key = ("test-namespace", "merlin-backups", uploaded["object_name"])
        original = self.client.objects[key]["data"]
        self.client.objects[key]["data"] = b"z" * len(original)
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.transport.upload_encrypted_backup(self.encrypted)

    def test_existing_object_with_wrong_metadata_is_not_accepted_as_replay(self):
        uploaded = self.transport.upload_encrypted_backup(self.encrypted)
        key = ("test-namespace", "merlin-backups", uploaded["object_name"])
        self.client.objects[key]["headers"]["opc-meta-merlin-sha256"] = "f" * 64
        with self.assertRaisesRegex(ObjectStorageConflict, "metadata mismatch"):
            self.transport.upload_encrypted_backup(self.encrypted)

    def test_rejects_wrong_object_name_digest_and_plaintext_zip(self):
        uploaded = self.transport.upload_encrypted_backup(self.encrypted)
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.transport.download_encrypted_backup(
                uploaded["object_name"], Path(self.temp.name) / "wrong.enc",
                expected_sha256="0" * 64,
            )
        with self.assertRaisesRegex(ValueError, "only Merlin encrypted"):
            self.transport.upload_encrypted_backup(self.backup)

    def test_download_does_not_overwrite_existing_file(self):
        uploaded = self.transport.upload_encrypted_backup(self.encrypted)
        destination = Path(self.temp.name) / "existing.enc"
        destination.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            self.transport.download_encrypted_backup(
                uploaded["object_name"], destination,
                expected_sha256=uploaded["sha256"],
            )
        self.assertEqual(destination.read_bytes(), b"keep")

    def test_environment_factory_fails_closed_without_namespace_and_bucket(self):
        with patch.dict("os.environ", {
            "MERLIN_BACKUP_OCI_NAMESPACE": "",
            "MERLIN_BACKUP_OCI_BUCKET": "",
        }):
            with self.assertRaisesRegex(RuntimeError, "unconfigured"):
                OciObjectStorageBackupTransport.from_environment()


if __name__ == "__main__":
    unittest.main()
