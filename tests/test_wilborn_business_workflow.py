import unittest
from wilborn_ops.business_workflow import evaluate
from wilborn_ops.research_snapshot import snapshot,replay

def candidate(record):
    a=dict(monthly_customers=10,price="100",variable_cost="25",fixed_cost="800")
    return dict(name="Fictional service",evidence_hashes=[record["sha256"]],
                assumptions=dict(pessimistic=a,baseline=a,optimistic=a))

class WorkflowTests(unittest.TestCase):
    def test_replay_and_plan(self):
        record=snapshot("https://www.sba.gov/",b"<p>Fictional fixture, not market evidence.</p>")
        result=evaluate([candidate(record)],[record])
        item=result["ranked"][0]
        self.assertTrue(item["evidence_integrity_replayed"])
        self.assertFalse(item["evidence_verified"])
        self.assertFalse(item["source_authenticity_verified"])
        self.assertEqual(item["evidence_data_class"],"unverified_research_input")
        self.assertEqual(item["ranking_basis"],"hypothetical_assumptions_only")
        self.assertFalse(result["verified_real"])
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["claims_verified"],0)
        with self.assertRaises(ValueError):
            evaluate([candidate(record)],[])

    def test_same_bytes_different_urls_cannot_replace_source_identity(self):
        body=b"<p>Fixture only.</p>"
        a=snapshot("https://www.sba.gov/",body)
        b=snapshot("https://www.nist.gov/",body)
        for records in ([a,b],[b,a]):
            with self.assertRaisesRegex(ValueError,"ambiguous"):
                evaluate([candidate(a)],records)
        self.assertTrue(evaluate([candidate(a)],[a,a])["ranked"][0]["evidence_integrity_replayed"])

    def test_unverified_class_survives_replay(self):
        r=snapshot("https://www.sba.gov/",b"<p>Entirely fabricated statement.</p>")
        self.assertEqual(replay(r).data_class,"unverified_research_input")
        for key,value in (("schema","public-research-snapshot-v1"),
                          ("data_class","verified_real"),
                          ("source_authenticity_verified",True),
                          ("source_authenticity_verified",0),
                          ("claims_verified",False)):
            with self.assertRaises(ValueError):
                replay(dict(r,**{key:value}))
