import hashlib, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_graph import build_graph
from register_inventory import RegistryError

class ProjectGraphTests(unittest.TestCase):
    def setUp(self):
        a=hashlib.sha256(b"archive").hexdigest(); f=hashlib.sha256(b"file").hexdigest()
        self.manifest={"manifest_version":"1.0","intake_id":"sha256:"+a,
          "archive":{"filename":"x.zip","sha256":a,"size_bytes":20},
          "file_count":1,"total_uncompressed_bytes":4,
          "files":[{"path":"src/a.py","sha256":f,"size_bytes":4,"classification":"source_code"}]}
    def test_exports_linked_provenance_graph(self):
        graph=build_graph(self.manifest,"merlin")
        self.assertEqual(len(graph["nodes"]),4)
        self.assertEqual(len(graph["edges"]),3)
        self.assertEqual(len({x["id"] for x in graph["nodes"]}),4)
    def test_rejects_unpaired_git_provenance(self):
        with self.assertRaises(RegistryError): build_graph(self.manifest,"merlin","org/repo",None)
if __name__=="__main__": unittest.main()
