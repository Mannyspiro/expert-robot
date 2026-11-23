"""Portable Second Brain source closure and fail-closed artifact inventory.

These fixtures guard the exact packaging defect discovered when the local
Second Brain controller and core modules were not in the Studio ZIP allowlist.
They do not replace a separately executed ZIP boot/restart smoke test.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "merlin_studio_portable_builder_under_test", ROOT / "portable" / "build_portable.py")
assert spec and spec.loader
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)
sys.path.insert(0, str(ROOT / "scripts"))
from verify_portable import verify

REQUIRED = {
    "second_brain.py",
    "web/second-brain.html",
    "core/python/merlin/knowledge_graph.py",
    "core/python/merlin/obsidian_vault_bridge.py",
    "core/python/merlin/obsidian_promotion.py",
    "core/python/merlin/obsidian_fts5.py",
}
FORBIDDEN = {
    "data/", "registry/", "settings.json", "workspace/",
    "models/model.gguf", "runtime/python/bin/python3",
}


class PortableSecondBrainTests(unittest.TestCase):
    def test_builder_contains_exact_optional_module_closure(self):
        payload, origins = portable.collect_sources()
        self.assertTrue(REQUIRED.issubset(payload.keys()), REQUIRED - payload.keys())
        self.assertEqual(len(payload), len(origins))
        self.assertTrue(all(payload[name] for name in REQUIRED))
        for name in REQUIRED:
            self.assertNotIn("data/", origins[name])
            self.assertNotIn(".obsidian", origins[name])

    def test_source_zip_verifies_and_contains_no_user_vault_or_weights(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "studio.zip"
            result = portable.build(output, include_native=False)
            checks = verify(output)
            self.assertTrue(checks["verified"])
            self.assertEqual(checks["file_count"], result["files"] - 1)
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                for file in REQUIRED:
                    self.assertIn("Merlin_Studio/" + file, names)
                self.assertFalse(any(
                    name.startswith("Merlin_Studio/" + prefix)
                    for name in names for prefix in FORBIDDEN
                ))
                manifest = json.loads(archive.read("Merlin_Studio/PACKAGE_MANIFEST.json"))
                self.assertFalse(manifest["contains_user_state"])
                self.assertFalse(manifest["contains_model_weights"])
                self.assertFalse(manifest["contains_python_runtime"])
                self.assertFalse(manifest["native_protocol"]["included"])

    def test_missing_second_brain_member_is_detected_by_manifest_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "studio.zip"
            mutated = Path(temp) / "missing.zip"
            portable.build(output, include_native=False)
            omitted = "Merlin_Studio/core/python/merlin/obsidian_promotion.py"
            with zipfile.ZipFile(output) as source, zipfile.ZipFile(mutated, "w") as destination:
                for member in source.infolist():
                    if member.filename != omitted:
                        destination.writestr(member, source.read(member.filename))
            with self.assertRaises(ValueError):
                verify(mutated)


if __name__ == "__main__":
    unittest.main()
