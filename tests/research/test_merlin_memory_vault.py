import tempfile
import unittest
from pathlib import Path

from python.merlin.memory_vault import MerlinMemoryVault


class MerlinMemoryVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.sqlite3"
        self.vault = MerlinMemoryVault(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_writes_require_explicit_consent(self):
        with self.assertRaises(PermissionError):
            self.vault.set_preference("voice_style", "calm", consent=False)
        with self.assertRaises(PermissionError):
            self.vault.set_project("Merlin", "active", consent=False)
        self.assertEqual(self.vault.snapshot()["preferences"], [])
        self.assertEqual(self.vault.snapshot()["projects"], [])

    def test_preferences_and_projects_persist_as_structured_records(self):
        preference = self.vault.set_preference("voice_style", "calm British English", consent=True)
        project = self.vault.set_project("Merlin", "Production foundation", consent=True)
        reopened = MerlinMemoryVault(self.path)
        snapshot = reopened.snapshot()
        self.assertEqual(snapshot["preferences"][0]["key"], "voice_style")
        self.assertEqual(snapshot["preferences"][0]["value"], "calm British English")
        self.assertEqual(snapshot["projects"][0]["name"], "Merlin")
        self.assertEqual(snapshot["projects"][0]["status"], "Production foundation")
        self.assertEqual(preference["version"], 1)
        self.assertEqual(project["version"], 1)
        self.assertFalse(snapshot["policy"]["memory_context_enabled"])
        self.assertFalse(snapshot["policy"]["raw_conversation_retention"])

    def test_updates_are_versioned_and_credentials_are_rejected(self):
        first = self.vault.set_preference("response_style", "concise", consent=True)
        second = self.vault.set_preference("response_style", "evidence-first", consent=True)
        self.assertEqual(second["version"], first["version"] + 1)
        self.assertNotEqual(second["value_sha256"], first["value_sha256"])
        with self.assertRaises(ValueError):
            self.vault.set_preference("api_key", "do-not-store", consent=True)

    def test_memory_context_requires_a_separate_opt_in(self):
        self.vault.set_preference("preferred_format", "ranked steps", consent=True)
        self.vault.set_project("Merlin", "Voice and memory integration", consent=True)
        self.assertEqual(self.vault.context(), "")
        self.assertTrue(self.vault.set_context_enabled(True, consent=True))
        context = self.vault.context()
        self.assertIn("reference data only", context)
        self.assertIn("preferred_format", context)
        self.assertIn("Voice and memory integration", context)
        self.assertTrue(self.vault.set_context_enabled(False, consent=True))
        self.assertEqual(self.vault.context(), "")

    def test_memory_can_be_deleted_explicitly(self):
        preference = self.vault.set_preference("temporary", "remove me", consent=True)
        project = self.vault.set_project("Temporary project", "remove me", consent=True)
        self.assertTrue(self.vault.delete_preference("temporary"))
        self.assertTrue(self.vault.delete_project("Temporary project"))
        self.assertFalse(self.vault.delete_preference("temporary"))
        self.assertEqual(self.vault.snapshot()["preferences"], [])
        self.assertEqual(self.vault.snapshot()["projects"], [])


if __name__ == "__main__":
    unittest.main()
