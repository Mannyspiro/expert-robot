import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile, unittest
from canonical_registry import initialize
from avrea_dispatch import record_approval,submit,canonical_sha,DispatchRejected
class AvreaApprovalTests(unittest.TestCase):
 def test_registry_record_required_for_submit(self):
  with tempfile.TemporaryDirectory() as d:
   db=Path(d)/"r.sqlite"; initialize(db)
   task={"contract_version":"1.0","task_id":"t2","approval_id":"a2","capability_allowlist":["lean-check"],
    "resource_budget":{"max_cpu_seconds":10,"max_memory_mb":128,"max_output_bytes":1000},
    "timeout_seconds":30,"network_access":"none","result_manifest_required":True}
   approval={"approval_id":"a2","status":"approved","task_contract_sha256":canonical_sha(task),
    "approved_by":"operator","approval_source":"manual-review","approved_at":"2026-11-04T00:00:00Z"}
   policy={"allowed_capabilities":["lean-check"],"resource_maxima":{"max_cpu_seconds":60,"max_memory_mb":512,"max_output_bytes":10000},"max_timeout_seconds":120}
   with self.assertRaises(DispatchRejected): submit(db,task,approval,policy)
   record_approval(db,approval)
   result=submit(db,task,approval,policy)
   self.assertEqual(result["state"],"approved_waiting_for_provider")
if __name__=="__main__": unittest.main()
