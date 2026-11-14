import base64
import json
from pathlib import Path
import struct
import tempfile
import unittest

from merlin.project_registry import MerlinRegistry
from merlin.registry_backup import MerlinRegistryBackup
from merlin.backup_encryption import (
    MAGIC,
    MerlinBackupEncryption,
)


class FakeKmsProvider:
    """Test-only deterministic wrapper; never use as a production key provider."""

    def __init__(self, key_id="test-kms-key/v1", wrapping_key=b"W" * 32):
        self.key_id = key_id
        self.wrapping_key = wrapping_key
        self.data_key = b"D" * 32

    def generate_data_key(self):
        wrapped = bytes(a ^ b for a, b in zip(self.data_key, self.wrapping_key))
        return self.key_id, self.data_key, wrapped

    def unwrap_data_key(self, key_id, wrapped_key):
        if key_id != self.key_id:
            raise ValueError("unknown KMS key version")
        return bytes(a ^ b for a, b in zip(wrapped_key, self.wrapping_key))


class MerlinBackupEncryptionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "registry"
        registry = MerlinRegistry(self.root)
        registry.register_project("merlin", "Merlin")
        registry.put_artifact("merlin", "research/source.txt", b"immutable backup source")
        self.backup_path = Path(self.temp.name) / "backup.zip"
        MerlinRegistryBackup(self.root).backup_to(self.backup_path)
        self.provider = FakeKmsProvider()
        self.encrypted_path = Path(self.temp.name) / "backup.mrb.enc"
        self.receipt = MerlinBackupEncryption.encrypt(
            self.backup_path, self.encrypted_path, self.provider,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_encrypt_decrypt_round_trip_authenticates_complete_backup(self):
        output = Path(self.temp.name) / "decrypted.zip"
        decrypted = MerlinBackupEncryption.decrypt(
            self.encrypted_path, output, self.provider,
        )
        self.assertTrue(output.is_file())
        self.assertEqual(decrypted["plaintext_sha256"], self.receipt["plaintext_sha256"])
        self.assertEqual(decrypted["envelope_sha256"], self.receipt["envelope_sha256"])
        self.assertTrue(decrypted["verified_backup"])
        self.assertTrue(MerlinRegistryBackup.verify_archive(output)["verified"])

    def test_tampered_ciphertext_fails_aes_gcm_authentication(self):
        raw = bytearray(self.encrypted_path.read_bytes())
        raw[-1] ^= 1
        tampered = Path(self.temp.name) / "tampered.enc"
        tampered.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "authentication failed"):
            MerlinBackupEncryption.decrypt(
                tampered, Path(self.temp.name) / "tampered-output.zip", self.provider,
            )

    def test_tampered_authenticated_header_fails_chunk_authentication(self):
        raw = self.encrypted_path.read_bytes()
        offset = len(MAGIC)
        header_length = struct.unpack(">I", raw[offset:offset + 4])[0]
        start = offset + 4
        header = json.loads(raw[start:start + header_length])
        header["nonce_prefix_b64"] = base64.b64encode(b"Z" * 8).decode("ascii")
        header_bytes = json.dumps(
            header, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        self.assertEqual(len(header_bytes), header_length)
        tampered = (
            raw[:offset] + struct.pack(">I", len(header_bytes))
            + header_bytes + raw[start + header_length:]
        )
        path = Path(self.temp.name) / "tampered-header.enc"
        path.write_bytes(tampered)
        with self.assertRaisesRegex(ValueError, "authentication failed"):
            MerlinBackupEncryption.decrypt(
                path, Path(self.temp.name) / "tampered-header-output.zip", self.provider,
            )

    def test_truncated_envelope_is_rejected(self):
        path = Path(self.temp.name) / "truncated.enc"
        path.write_bytes(self.encrypted_path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "truncated"):
            MerlinBackupEncryption.decrypt(
                path, Path(self.temp.name) / "truncated-output.zip", self.provider,
            )

    def test_wrong_kms_key_version_fails_closed(self):
        wrong_provider = FakeKmsProvider(key_id="different-kms-key/v2")
        with self.assertRaisesRegex(ValueError, "unknown KMS key version"):
            MerlinBackupEncryption.decrypt(
                self.encrypted_path, Path(self.temp.name) / "wrong-key-output.zip",
                wrong_provider,
            )

    def test_encrypt_rejects_invalid_backup_and_existing_destination(self):
        with self.assertRaises(FileExistsError):
            MerlinBackupEncryption.encrypt(
                self.backup_path, self.encrypted_path, self.provider,
            )
        invalid = Path(self.temp.name) / "invalid.zip"
        invalid.write_bytes(b"not a verified backup")
        with self.assertRaisesRegex(ValueError, "ZIP archive"):
            MerlinBackupEncryption.encrypt(
                invalid, Path(self.temp.name) / "invalid.enc", self.provider,
            )

    def test_invalid_chunk_sizes_are_rejected(self):
        for chunk_size in (True, 1, 32 * 1024, 16 * 1024 * 1024 + 1):
            with self.assertRaisesRegex(ValueError, "chunk_size"):
                MerlinBackupEncryption.encrypt(
                    self.backup_path,
                    Path(self.temp.name) / f"bad-{chunk_size}.enc",
                    self.provider,
                    chunk_size=chunk_size,
                )


if __name__ == "__main__":
    unittest.main()
