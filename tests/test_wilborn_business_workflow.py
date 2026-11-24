import unittest
from wilborn_ops.business_workflow import evaluate
from wilborn_ops.research_snapshot import snapshot
class WorkflowTests(unittest.TestCase):
    def test_replay_and_plan(self):
        record=snapshot("https://www.sba.gov/",b"<p>Fictional fixture, not market evidence.</p>")
        a=dict(monthly_customers=10,price="100",variable_cost="25",fixed_cost="800")
        candidate=dict(name="Fictional service",evidence_hashes=[record["sha256"]],
                       assumptions=dict(pessimistic=a,baseline=a,optimistic=a))
        result=evaluate([candidate],[record])
        self.assertTrue(result["ranked"][0]["evidence_integrity_replayed"])
        self.assertFalse(result["ranked"][0]["evidence_verified"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["claims_verified"],0)
        with self.assertRaises(ValueError):
            evaluate([candidate],[])
