import unittest
from wilborn_ops.research_queue import build_research_queue

class ResearchQueueTests(unittest.TestCase):
    def test_ranked_deterministic_bounded_queue(self):
        summary={"environment":"demo","data_class":"synthetic",
                 "counts":{"tool_denied":7,"unexpected_tool":2,"integrity_failure":1}}
        first=build_research_queue(summary,max_tasks=2)
        second=build_research_queue(summary,max_tasks=2)
        self.assertEqual(first,second)
        self.assertEqual([task.finding_kind for task in first],
                         ["integrity_failure","unexpected_tool"])
        self.assertTrue(all(task.requires_independent_review for task in first))
        self.assertTrue(all(task.environment=="demo" for task in first))

    def test_reject_production_and_invalid_budget(self):
        with self.assertRaises(PermissionError):
            build_research_queue({"environment":"production","data_class":"real","counts":{}})
        with self.assertRaises(ValueError):
            build_research_queue({"environment":"demo","data_class":"synthetic","counts":{}},
                                 max_tasks=0)

    def test_empty_is_not_a_finding(self):
        self.assertEqual(build_research_queue(
            {"environment":"demo","data_class":"synthetic","counts":{}}),[])
