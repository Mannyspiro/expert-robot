import unittest
from wilborn_ops.research_snapshot import snapshot,replay

class SnapshotTests(unittest.TestCase):
    def test_replay(self):
        record=snapshot("https://www.sba.gov/",b"<p>Fictional test fixture</p>")
        self.assertEqual(replay(record).text,"Fictional test fixture")
        self.assertEqual(record["claims_verified"],0)
    def test_tampering(self):
        record=snapshot("https://www.sba.gov/",b"<p>Fixture</p>")
        for key,value in (("sha256","0"*64),("data_class","real"),("claims_verified",1),("body_base64","!")):
            with self.assertRaises(ValueError):
                replay(dict(record,**{key:value}))
