import hashlib, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hermes_event import build_event
from register_inventory import RegistryError

class HermesEventTests(unittest.TestCase):
    def setUp(self):
        archive=hashlib.sha256(b"a").hexdigest()
        self.manifest={"manifest_version":"1.0","intake_id":"sha256:"+archive,
          "archive":{"filename":"a.zip","sha256":archive,"size_bytes":1},
          "file_count":0,"total_uncompressed_bytes":0,"files":[]}
    def test_event_is_stable_except_timestamp(self):
        a=build_event(self.manifest,"proj-1")
        b=build_event(self.manifest,"proj-1")
        self.assertEqual(a["event_id"],b["event_id"])
    def test_requires_paired_git_provenance(self):
        with self.assertRaises(RegistryError): build_event(self.manifest,"proj-1","org/repo",None)
    def test_rejects_short_commit_sha(self):
        with self.assertRaises(RegistryError): build_event(self.manifest,"proj-1","org/repo","abc")
if __name__=="__main__": unittest.main()
