import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from avrea_dispatch import validate_task, DispatchRejected, canonical_sha


def fixture():
    task = {
        "contract_version": "1.0",
        "task_id": "t1",
        "approval_id": "a1",
        "capability_allowlist": ["lean-check"],
        "resource_budget": {
            "max_cpu_seconds": 10,
            "max_memory_mb": 128,
            "max_output_bytes": 1000,
        },
        "timeout_seconds": 30,
        "network_access": "none",
        "result_manifest_required": True,
    }
    task["task_contract_sha256"] = canonical_sha(task)
    approval = {
        "approval_id": "a1",
        "status": "approved",
        "task_contract_sha256": canonical_sha(task),
    }
    policy = {
        "allowed_capabilities": ["lean-check"],
        "resource_maxima": {
            "max_cpu_seconds": 60,
            "max_memory_mb": 512,
            "max_output_bytes": 10000,
        },
        "max_timeout_seconds": 120,
    }
    return task, approval, policy


class AvreaDispatchTests(unittest.TestCase):
    def test_exact_approval_and_budget_required(self):
        task, approval, policy = fixture()
        self.assertEqual(validate_task(task, approval, policy), canonical_sha(task))
        approval["task_contract_sha256"] = "0" * 64
        with self.assertRaises(DispatchRejected):
            validate_task(task, approval, policy)

    def test_mutated_task_fails_exact_hash_check(self):
        task, approval, policy = fixture()
        task["timeout_seconds"] = 31
        with self.assertRaises(DispatchRejected):
            validate_task(task, approval, policy)

    def test_capability_escalation_is_rejected(self):
        task, approval, policy = fixture()
        task["capability_allowlist"].append("unapproved-capability")
        task["task_contract_sha256"] = canonical_sha(task)
        approval["task_contract_sha256"] = canonical_sha(task)
        with self.assertRaises(DispatchRejected):
            validate_task(task, approval, policy)

    def test_network_access_is_fail_closed(self):
        task, approval, policy = fixture()
        task["network_access"] = "enabled"
        task["task_contract_sha256"] = canonical_sha(task)
        approval["task_contract_sha256"] = canonical_sha(task)
        with self.assertRaises(DispatchRejected):
            validate_task(task, approval, policy)

    def test_budget_above_policy_is_rejected(self):
        task, approval, policy = fixture()
        task["resource_budget"]["max_memory_mb"] = 1024
        task["task_contract_sha256"] = canonical_sha(task)
        approval["task_contract_sha256"] = canonical_sha(task)
        with self.assertRaises(DispatchRejected):
            validate_task(task, approval, policy)

    def test_budget_shape_must_match_policy(self):
        task, approval, policy = fixture()
        task["resource_budget"]["unexpected"] = 1
        task["task_contract_sha256"] = canonical_sha(task)
        approval["task_contract_sha256"] = canonical_sha(task)
        with self.assertRaises(DispatchRejected):
            validate_task(task, approval, policy)


if __name__ == "__main__":
    unittest.main()
