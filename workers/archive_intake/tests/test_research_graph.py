import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile, unittest, json
from canonical_registry import initialize,register_project,connect
from research_graph import export_graph
class ResearchGraphTests(unittest.TestCase):
 def test_graph_links_receipts_metadata_and_wiring(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"r.sqlite"; initialize(db); register_project(db,"p","Project")
   with connect(db) as cx:
    cx.execute("INSERT INTO intakes(intake_id,archive_sha256,archive_filename,archive_size_bytes,manifest_sha256,registered_at,file_count,total_uncompressed_bytes) VALUES(?,?,?,?,?,?,?,?)",("i1","a"*64,"a.zip",1,"b"*64,"2026-01-01T00:00:00Z",1,1))
    cx.execute("INSERT INTO artifacts VALUES(?,?,?,?,?)",("i1","model.step","c"*64,1,"cad_model"))
    cx.execute("INSERT INTO project_intakes VALUES(?,?,?)",("p","i1","2026-01-01T00:00:00Z"))
    receipt={"receipt_id":"r1","verifier_id":"CACE","result":"passed","evidence_class":"test"}
    cx.execute("INSERT INTO verification_receipts VALUES(?,?,?,?,?,?,?,?)",("r1","c"*64,"CACE","1","passed","test",json.dumps(receipt),"2026-01-01T00:00:00Z"))
    cx.execute("INSERT INTO engineering_metadata VALUES(?,?,?,?)",("c"*64,"p",json.dumps({"units":{"length":"mm"}}),"2026-01-01T00:00:00Z"))
    cx.execute("INSERT INTO wiring_connections VALUES(?,?,?,?,?,?,?,?)",("p","w1","J1","1","R1","1","VCC","{}"))
   graph=export_graph(db,"p"); ids={x["id"] for x in graph["nodes"]}
   self.assertTrue(all(e["from"] in ids and e["to"] in ids for e in graph["edges"]))
   self.assertTrue(any(x["type"]=="VerificationReceipt" for x in graph["nodes"]))
if __name__=="__main__": unittest.main()
