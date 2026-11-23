#!/usr/bin/env python3
"""Fail-closed tests for the data-only Atlas staging adapter."""
import hashlib, importlib.util, json, tempfile, unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "tools" / "atlas_bridge_inbox.py"
spec = importlib.util.spec_from_file_location("atlas_bridge_inbox", MODULE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

def good_task():
    obj = {
        "schema": "atlas.bridge.v1", "project": "SGK",
        "task_type": "lean_theorem_proof", "claim_id": "DC000001",
        "claim_sha256": "a"*64, "claim_text": "2 is prime",
        "assumptions": "positive natural integers",
        "source_url": "https://mathworld.wolfram.com/PrimeFactorization.html",
        "privileges": "NONE", "network": "NONE", "status": "PROPOSED_ONLY",
        "qualification": "MUST_REVERIFY_AT_PINNED_TARGET"
    }
    obj["payload_sha256"] = hashlib.sha256(bridge.canonical(obj)).hexdigest()
    return obj

class BridgeTests(unittest.TestCase):
    def check(self, obj):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "task.json"
            p.write_text(json.dumps(obj), encoding="utf-8")
            return bridge.inspect_task(p, "SGK")

    def test_valid_only_stages(self):
        result = self.check(good_task())
        self.assertEqual(result["review_state"], "UNTRUSTED_STAGED")
        self.assertFalse(result["proof_accepted"])

    def test_must_not_gain_authority(self):
        obj = good_task()
        obj["privileges"] = "NETWORK_ACCESS"
        with self.assertRaises(ValueError):
            self.check(obj)

    def test_hash_tampering(self):
        obj = good_task()
        obj["claim_text"] = "unverified replacement"
        with self.assertRaises(ValueError):
            self.check(obj)

    def test_bad_proof_status(self):
        obj = good_task()
        obj["status"] = "PASS"
        with self.assertRaises(ValueError):
            self.check(obj)

if __name__ == "__main__":
    unittest.main()
