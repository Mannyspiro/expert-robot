import tempfile, unittest
from pathlib import Path
from canonical_registry import initialize, register_project, query_projects, query_artifacts
class RegistryApiTests(unittest.TestCase):
 def test_project_register_and_read_query(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"registry.sqlite"; initialize(db)
   register_project(db,"merlin-demo","Merlin Demo")
   self.assertEqual(query_projects(db)[0]["project_id"],"merlin-demo")
   self.assertEqual(query_artifacts(db,"merlin-demo"),[])
if __name__=="__main__": unittest.main()
