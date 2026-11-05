import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import unittest
from cace_adapter import _statuses
class CaceAdapterTests(unittest.TestCase):
 def test_statuses_are_extracted_without_inventing_pass(self):
  self.assertEqual(_statuses({"verification":{"status":"PASS"},"other":"not evidence"}),["PASS"])
  self.assertEqual(_statuses({"message":"completed"}),[])
if __name__=="__main__": unittest.main()
