import unittest

from merlin.intent_compiler import Asset, ContinuityState, IntentSpec, compile_directive


class IntentCompilerTests(unittest.TestCase):
    def make_intent(self, **overrides):
        values = dict(
            goal="Investigate a proposed spectral invariant.",
            domain="mathematics",
            deliverable="A reproducible experiment plan and reviewable directive.",
            constraints=("Preserve supplied assumptions.",),
            exclusions=("Do not claim a proof without formal evidence.",),
            success_criteria=("Identify falsifiable tests.", "Record missing evidence."),
            audience="Merlin research subsystem",
            target_backend="hermes.research",
        )
        values.update(overrides)
        return IntentSpec(**values)

    def test_compile_is_deterministic_and_hash_bound(self):
        first = compile_directive(self.make_intent(), [])
        second = compile_directive(self.make_intent(), [])
        self.assertEqual(first, second)
        self.assertEqual(len(first["directive_sha256"]), 64)
        self.assertIn("Do not execute external actions", first["directive"])
        self.assertIn("None supplied", first["directive"])

    def test_changed_goal_changes_directive_digest(self):
        first = compile_directive(self.make_intent(), [])
        second = compile_directive(self.make_intent(goal="Investigate a different invariant."), [])
        self.assertNotEqual(first["directive_sha256"], second["directive_sha256"])

    def test_asset_digest_is_validated_and_bound(self):
        asset = Asset("source-1", "paper.pdf", "document", "a" * 64)
        result = compile_directive(self.make_intent(), [asset])
        self.assertIn("sha256=" + "a" * 64, result["directive"])
        with self.assertRaises(ValueError):
            compile_directive(self.make_intent(), [Asset("source-1", "paper.pdf", "document", "bad")])

    def test_duplicate_asset_ids_are_rejected(self):
        asset = Asset("source-1", "paper.pdf", "document", "a" * 64)
        with self.assertRaises(ValueError):
            compile_directive(self.make_intent(), [asset, asset])

    def test_unsupported_domain_is_rejected(self):
        with self.assertRaises(ValueError):
            compile_directive(self.make_intent(domain="unknown"), [])

    def test_continuity_checkpoint_is_bound(self):
        continuity = ContinuityState("checkpoint-1", "Prior verified state", ("node-1",), "Run next experiment")
        result = compile_directive(self.make_intent(), [], continuity)
        self.assertIn("checkpoint_id=checkpoint-1", result["directive"])
        self.assertIn("Preserve established identities and state", result["directive"])


if __name__ == "__main__":
    unittest.main()
