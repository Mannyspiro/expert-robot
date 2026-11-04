import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from register_inventory import RegistryError, register_manifest

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"
        self.database = self.root / "registry.sqlite3"
        self.archive_sha = hashlib.sha256(b"archive").hexdigest()
        self.file_sha = hashlib.sha256(b"content").hexdigest()
        self.data = {
            "manifest_version":"1.0",
            "intake_id":"sha256:" + self.archive_sha,
            "archive":{"filename":"source.zip","sha256":self.archive_sha,"size_bytes":100},
            "file_count":1,"total_uncompressed_bytes":7,
            "files":[{"path":"src/main.py","sha256":self.file_sha,"size_bytes":7,"classification":"source_code"}]
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.data,sort_keys=True),encoding="utf-8")

    def test_registers_and_is_idempotent(self):
        self.write_manifest()
        first = register_manifest(self.manifest,self.database)
        second = register_manifest(self.manifest,self.database)
        self.assertEqual(first["status"],"registered")
        self.assertEqual(second["status"],"already_registered")

    def test_rejects_total_size_mismatch(self):
        self.data["total_uncompressed_bytes"] = 99
        self.write_manifest()
        with self.assertRaises(RegistryError):
            register_manifest(self.manifest,self.database)

    def test_rejects_archive_id_mismatch(self):
        self.data["intake_id"] = "sha256:" + ("0" * 64)
        self.write_manifest()
        with self.assertRaises(RegistryError):
            register_manifest(self.manifest,self.database)

if __name__ == "__main__":
    unittest.main()
