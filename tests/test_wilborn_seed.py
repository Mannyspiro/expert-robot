import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from wilborn_ops.seed import load_fixture, seed_demo
from wilborn_ops.store import CaseStore

class SyntheticSeedTests(unittest.TestCase):
    def test_bundled_fixture_only_and_labeled(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"demo.db")
            report=seed_demo(store)
            self.assertEqual(report["created"],8)
            self.assertEqual(report["data_class"],"synthetic")
            self.assertEqual(len(store.list_cases()),8)
            with self.assertRaises(ValueError):
                seed_demo(store)
            store.close()

    def test_external_paths_and_unknown_fixtures_rejected(self):
        for name in ("../clients", "/tmp/client.csv", "production",
                     "workshop_v1.json", "https://example.org/export"):
            with self.assertRaises(PermissionError):
                load_fixture(name)

    def test_fixture_tamper_rejected(self):
        class FakeResource:
            def read_text(self,encoding):
                return json.dumps({"fixture_id":"wilborn-workshop-v1",
                                   "data_class":"real","environment":"production",
                                   "generator":"hand-authored-fictional-fixture",
                                   "cases":[]})
        class FakeFiles:
            def joinpath(self,name):
                return FakeResource()
        with patch("wilborn_ops.seed.files",return_value=FakeFiles()):
            with self.assertRaises(PermissionError):
                load_fixture("workshop_v1")

    def test_invalid_store_rejected(self):
        with self.assertRaises(TypeError):
            seed_demo(object())
