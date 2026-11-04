import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from merlin_archive_intake import IntakeError, IntakeLimits, intake_archive

class ArchiveIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "input.zip"
        self.output = self.root / "out"

    def tearDown(self):
        self.temp.cleanup()

    def make_zip(self, entries):
        with zipfile.ZipFile(self.archive, "w") as zf:
            for name, data in entries:
                zf.writestr(name, data)

    def test_extracts_hashes_and_never_executes(self):
        self.make_zip([("src/main.py", "print('not run')"),
                       ("proof/Main.lean", "theorem t : True := True.intro")])
        manifest = intake_archive(self.archive, self.output)
        self.assertEqual(manifest["file_count"], 2)
        self.assertEqual((self.output/"src/main.py").read_text(), "print('not run')")
        self.assertEqual(manifest["execution_policy"], "contents_inspected_only_never_executed")
        saved = json.loads((self.output/"merlin-intake-manifest.json").read_text())
        self.assertEqual(saved["file_count"], 2)

    def test_rejects_parent_traversal(self):
        self.make_zip([("../escape.txt", "no")])
        with self.assertRaises(IntakeError):
            intake_archive(self.archive, self.output)
        self.assertFalse(self.output.exists())

    def test_rejects_absolute_paths(self):
        self.make_zip([("/tmp/escape.txt", "no")])
        with self.assertRaises(IntakeError):
            intake_archive(self.archive, self.output)

    def test_rejects_file_count_limit(self):
        self.make_zip([("a.txt","a"),("b.txt","b")])
        with self.assertRaises(IntakeError):
            intake_archive(self.archive,self.output,IntakeLimits(max_files=1))

    def test_rejects_member_size_limit(self):
        self.make_zip([("large.bin","0123456789")])
        with self.assertRaises(IntakeError):
            intake_archive(self.archive,self.output,IntakeLimits(max_member_uncompressed=5))

    def test_refuses_existing_destination(self):
        self.make_zip([("a.txt","a")])
        self.output.mkdir()
        with self.assertRaises(IntakeError):
            intake_archive(self.archive,self.output)

if __name__ == "__main__":
    unittest.main()
