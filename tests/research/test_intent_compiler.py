import unittest

from python.merlin.intent_compiler import (
    Asset, ContinuityState, IntentSpec, compile_directive,
)


class IntentCompilerTests(unittest.TestCase):
    def asset(self, **changes):
        values = dict(
            asset_id="character-ref-01", name="Character reference",
            kind="image", sha256="a" * 64, role="identity_authority",
        )
        values.update(changes)
        return Asset(**values)

    def test_compiles_goal_assets_constraints_and_success_criteria(self):
        intent = IntentSpec(
            goal="Create a continuous short film",
            domain="video",
            deliverable="Timed model-specific scene directions",
            constraints=("preserve character identity", "slow camera movement"),
            exclusions=("no hard cuts",),
            success_criteria=("wardrobe remains consistent",),
            target_backend="video-model-x",
            duration_seconds=30,
        )
        result = compile_directive(intent, [self.asset()])
        self.assertEqual(result["domain"], "video")
        self.assertIn("sha256=" + "a" * 64, result["directive"])
        self.assertIn("no hard cuts", result["directive"])
        self.assertIn("DURATION_SECONDS: 30", result["directive"])
        self.assertEqual(result["asset_ids"], ["character-ref-01"])
        self.assertEqual(len(result["directive_sha256"]), 64)

    def test_continuity_state_is_carried_forward(self):
        state = ContinuityState(
            checkpoint_id="clip-02",
            prior_state="last frame: character exits doorway",
            stable_entity_ids=("character-01", "location-02"),
            next_step="continue movement into hallway",
        )
        result = compile_directive(
            IntentSpec("Continue scene", "video", "next clip"),
            [self.asset()], state,
        )
        self.assertIn("character exits doorway", result["directive"])
        self.assertIn("character-01,location-02", result["directive"])
        self.assertEqual(result["continuity_checkpoint_id"], "clip-02")

    def test_duplicate_assets_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate asset_id"):
            compile_directive(
                IntentSpec("Research", "research", "evidence map"),
                [self.asset(), self.asset()],
            )

    def test_bad_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "64-character"):
            compile_directive(
                IntentSpec("Research", "research", "evidence map"),
                [self.asset(sha256="bad")],
            )

    def test_unsupported_domain_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported domain"):
            compile_directive(IntentSpec("Do thing", "magic", "result"), [])

    def test_external_execution_is_not_implicitly_authorized(self):
        result = compile_directive(
            IntentSpec("Deploy", "software", "deployment plan"), []
        )
        self.assertIn("Do not execute external actions", result["directive"])


if __name__ == "__main__":
    unittest.main()
