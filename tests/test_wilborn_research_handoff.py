import copy
import unittest
from wilborn_ops.research_handoff import export_handoff,verify_handoff

COMMIT="a"*40
RUN=45286212534

class ResearchHandoffTests(unittest.TestCase):
    def test_deterministic_nonexecuting_handoff(self):
        summary={"environment":"demo","data_class":"synthetic",
                 "counts":{"unexpected_tool":3,"tool_denied":2}}
        one=export_handoff(summary,source_commit=COMMIT,ci_run=RUN)
        two=export_handoff(summary,source_commit=COMMIT,ci_run=RUN)
        self.assertEqual(one,two)
        self.assertTrue(verify_handoff(one))
        self.assertTrue(all(not task["execution_authorized"] and
                            not task["production_change_authorized"]
                            for task in one["payload"]["tasks"]))

    def test_tampering_fails(self):
        handoff=export_handoff({"environment":"demo","data_class":"synthetic",
                               "counts":{"integrity_failure":1}},
                              source_commit=COMMIT,ci_run=RUN)
        altered=copy.deepcopy(handoff)
        altered["payload"]["tasks"][0]["execution_authorized"]=True
        with self.assertRaises(PermissionError):
            verify_handoff(altered)
        altered=copy.deepcopy(handoff)
        altered["sha256"]="0"*64
        with self.assertRaises(ValueError):
            verify_handoff(altered)
        altered=copy.deepcopy(handoff)
        altered["payload"]["environment"]="production"
        with self.assertRaises(PermissionError):
            verify_handoff(altered)

    def test_invalid_evidence_identity(self):
        with self.assertRaises(ValueError):
            export_handoff({"environment":"demo","data_class":"synthetic","counts":{}},
                           source_commit="main",ci_run=RUN)
