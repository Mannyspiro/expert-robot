import tempfile, unittest
from pathlib import Path
from canonical_registry import initialize
from hermes_outbox import enqueue,claim,acknowledge,retry
class HermesOutboxTests(unittest.TestCase):
 def test_lease_retry_ack_lifecycle(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"r.sqlite"; initialize(db)
   event={"event_id":"e1","event_type":"merlin.test.v1"}
   enqueue(db,event); lease=claim(db,"worker-a")
   self.assertEqual(lease["event_id"],"e1")
   retry(db,"e1","worker-a","temporary")
   lease=claim(db,"worker-b")
   result=acknowledge(db,"e1","worker-b",{"event_id":"e1","status":"accepted"})
   self.assertEqual(result["state"],"acked")
if __name__=="__main__": unittest.main()
