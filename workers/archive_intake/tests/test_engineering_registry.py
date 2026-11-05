import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile, unittest
from canonical_registry import initialize,register_project
from engineering_registry import store_wiring
class EngineeringRegistryTests(unittest.TestCase):
 def test_wiring_requires_registered_project(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"registry.sqlite"; initialize(db); register_project(db,"p","Project")
   conn=[{"connection_id":"c1","from_node":"J1","from_pin":"1","to_node":"R1","to_pin":"1","net_name":"VCC"}]
   self.assertEqual(store_wiring(db,"p",conn)["net_count"],1)
if __name__=="__main__": unittest.main()
