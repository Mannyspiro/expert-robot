import json
import unittest
from merlin.titan_crypto_lab import hermes_titan_research_executor


class Context:
    task_id = "titan-task-001"
    hypothesis_id = "H-TITAN-001"


class TitanHermesExecutorTests(unittest.TestCase):
    def test_emits_deterministic_matrix_as_research_artifact(self):
        task = {"stage": "research", "objective": "Research Titan context-bound envelope"}
        result = hermes_titan_research_executor(task, Context())
        report = json.loads(result["artifact_bytes"])
        self.assertEqual(report["schema"], "titan-hermes-research-output/1")
        self.assertEqual(report["task_id"], Context.task_id)
        self.assertEqual(report["hypothesis_id"], Context.hypothesis_id)
        self.assertFalse(result["metadata"]["cryptographic_operations_performed"])
        self.assertIn("no cryptographic operations", result["summary"])

    def test_rejects_non_titan_research_task(self):
        with self.assertRaisesRegex(ValueError, "explicitly identify Titan"):
            hermes_titan_research_executor(
                {"stage": "research", "objective": "Research an unrelated topic"}, Context()
            )


if __name__ == "__main__":
    unittest.main()
