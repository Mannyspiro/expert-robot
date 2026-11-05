import unittest
from cad_mcfc_model import transform_point,multiply,validate_wiring,validate_simulation
class CadMcfcTests(unittest.TestCase):
 def test_affine_transform(self):
  m=[[1,0,0,2],[0,1,0,3],[0,0,1,4],[0,0,0,1]]
  self.assertEqual(transform_point(m,[1,1,1]),[3,4,5])
 def test_wiring_net(self):
  result=validate_wiring([{"connection_id":"c1","from_node":"J1","from_pin":"1","to_node":"R1","to_pin":"1","net_name":"VCC"}])
  self.assertIn("VCC",result["nets"])
if __name__=="__main__": unittest.main()
