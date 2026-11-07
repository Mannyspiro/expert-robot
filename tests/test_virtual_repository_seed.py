import json
import tempfile
import unittest
from pathlib import Path

from python.merlin.virtual_repository_seed import build_repository_seed


class VirtualRepositorySeedTests(unittest.TestCase):
    def test_seed_is_deterministic_and_excludes_sensitive_generated_and_binary_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("# Merlin\n", encoding="utf-8")
            (root / "pyproject.toml").write_text("[project]\nname='merlin'\n", encoding="utf-8")
            (root / "python/merlin").mkdir(parents=True)
            (root / "python/merlin/app.py").write_text("APP_READY = True\n", encoding="utf-8")
            (root / "python/merlin/secrets.json").write_text('{"token":"do-not-copy"}', encoding="utf-8")
            (root / "python/merlin/.env").write_text("TOKEN=do-not-copy", encoding="utf-8")
            (root / "python/merlin/__pycache__").mkdir()
            (root / "python/merlin/__pycache__/cache.py").write_text("CACHE = True", encoding="utf-8")
            (root / "ui").mkdir()
            (root / "ui/index.html").write_text("<main>Merlin</main>", encoding="utf-8")
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/ci.yml").write_text("name: CI\n", encoding="utf-8")
            (root / "assets").mkdir()
            (root / "assets/image.png").write_bytes(b"not text")
            (root / "python/merlin/large.txt").write_text("x" * 100, encoding="utf-8")

            seed, manifest = build_repository_seed(root, max_file_bytes=50)
            seed_again, manifest_again = build_repository_seed(root, max_file_bytes=50)
            self.assertEqual(seed, seed_again)
            self.assertEqual(manifest["tree_sha256"], manifest_again["tree_sha256"])
            self.assertIn("python/merlin/app.py", seed)
            self.assertIn("ui/index.html", seed)
            self.assertIn(".github/workflows/ci.yml", seed)
            self.assertIn("merlin/SEED_MANIFEST.json", seed)
            self.assertNotIn("python/merlin/secrets.json", seed)
            self.assertNotIn("python/merlin/.env", seed)
            self.assertNotIn("python/merlin/__pycache__/cache.py", seed)
            self.assertNotIn("assets/image.png", seed)
            self.assertFalse(manifest["sensitive_files_included"])
            decoded = json.loads(seed["merlin/SEED_MANIFEST.json"])
            self.assertEqual(decoded["tree_sha256"], manifest["tree_sha256"])
            reasons = {row["path"]: row["reason"] for row in manifest["excluded"]}
            self.assertEqual(reasons["python/merlin/secrets.json"], "sensitive_name")
            self.assertEqual(reasons["python/merlin/large.txt"], "file_size_limit")

    def test_seed_refuses_silent_partial_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "README.md").write_text("readme", encoding="utf-8")
            (root / "python").mkdir()
            (root / "python/app.py").write_text("APP = True", encoding="utf-8")
            with self.assertRaises(ValueError):
                build_repository_seed(root, max_files=1)
            with self.assertRaises(ValueError):
                build_repository_seed(root, max_total_bytes=1)

    def test_seed_requires_existing_repository_root(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                build_repository_seed(Path(temp) / "missing")


if __name__ == "__main__":
    unittest.main()
