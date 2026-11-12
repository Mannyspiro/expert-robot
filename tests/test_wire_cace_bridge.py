import unittest

from merlin.wire_cace_bridge import make_cace_wire_evidence_verifier


class FakeCaceAdapter:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or {
            "verification_status": "verified",
            "verifier_id": "cace:independent-reviewer",
            "receipt_artifact_sha256": "b" * 64,
            "additional_bindings": {},
        }

    def verify_artifact(self, **kwargs):
        self.calls.append(kwargs)
        result = dict(self.result)
        result["additional_bindings"] = kwargs["additional_bindings"]
        return result


class WireCaceBridgeTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeCaceAdapter()
        self.verify = make_cace_wire_evidence_verifier(
            self.adapter,
            project_id="merlin",
            repository="Mannyspiro/expert-robot",
            commit_sha="a" * 40,
            requester_id="merlin-wire-engine",
            tool_identity="merlin-wire-qualification/0.2",
        )

    def request(self):
        return {
            "requirement": "component_datasheets",
            "artifact_sha256": "c" * 64,
            "evidence_record_sha256": "d" * 64,
            "evidence": {
                "artifact_kind": "engineering-evidence",
                "artifact_schema": "merlin-component-datasheet-evidence/1",
                "logical_path": "evidence/components/supply.json",
            },
        }

    def test_calls_cace_with_exact_requirement_and_record_bindings(self):
        result = self.verify(self.request())
        call = self.adapter.calls[0]
        self.assertEqual(call["artifact_sha256"], "c" * 64)
        self.assertEqual(call["additional_bindings"], {
            "wire_requirement": "component_datasheets",
            "evidence_record_sha256": "d" * 64,
        })
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertEqual(result["bindings"]["requirement"], "component_datasheets")
        self.assertEqual(result["bindings"]["artifact_sha256"], "c" * 64)
        self.assertEqual(result["bindings"]["evidence_record_sha256"], "d" * 64)

    def test_rejected_cace_result_is_not_promoted_to_verified(self):
        self.adapter.result["verification_status"] = "rejected"
        result = self.verify(self.request())
        self.assertEqual(result["verification_status"], "REJECTED")

    def test_missing_registry_metadata_is_rejected(self):
        request = self.request()
        del request["evidence"]["logical_path"]
        with self.assertRaisesRegex(ValueError, "logical_path"):
            self.verify(request)
        self.assertEqual(self.adapter.calls, [])

    def test_malformed_subject_digest_is_rejected(self):
        request = self.request()
        request["evidence_record_sha256"] = "not-a-digest"
        with self.assertRaisesRegex(ValueError, "record digest"):
            self.verify(request)
        self.assertEqual(self.adapter.calls, [])


if __name__ == "__main__":
    unittest.main()
