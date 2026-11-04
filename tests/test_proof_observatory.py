import tempfile
import unittest
from pathlib import Path

from merlin.proof_observatory import (
    CrossDomainLink, GoalKey, ProofAttempt, ProofObservatory,
    object_view_engineering_links, rank_strategies,
)


def attempt(attempt_id, tactics=("rfl",), statement="a", assumptions="b",
            outcome="success", qualified=True, heartbeats=100, elapsed=2.0):
    import hashlib
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    return ProofAttempt(
        attempt_id=attempt_id,
        goal=GoalKey("MathAI.Example.identity", digest(statement), digest(assumptions),
                     "algebra", ("cartesian-2d",)),
        tactic_sequence=tactics,
        outcome=outcome,
        failure_stage=None if outcome == "success" else "elaboration",
        elapsed_ms=elapsed,
        heartbeats=heartbeats,
        peak_memory_bytes=1024,
        source_commit="a" * 40,
        source_sha256=digest("source"),
        lean_version="4.34.0",
        mathlib_revision="locked-mathlib-revision",
        import_closure_sha256=digest("imports"),
        kernel_checked=qualified,
        contains_sorry=not qualified,
        axiom_dependencies=("propext",),
        exact_target_declaration=qualified,
        workflow_run_url="https://github.com/Mannyspiro/expert-robot/actions/runs/12345" if qualified else None,
    )


class ProofObservatoryTests(unittest.TestCase):
    def test_append_only_store_and_hash_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProofObservatory(Path(directory) / "observatory.sqlite")
            store.record_attempt(attempt("a1"))
            store.record_attempt(attempt("a2", outcome="failure", qualified=False))
            self.assertTrue(store.verify_chain())
            self.assertEqual(len(store.attempts()), 2)
            store.close()

    def test_attempt_rejects_bad_provenance(self):
        bad = attempt("bad")
        bad = ProofAttempt(**{**bad.__dict__, "source_commit": "not-a-sha"})
        with self.assertRaises(ValueError):
            bad.validate()

    def test_strategy_requires_three_qualified_repetitions(self):
        rows = [attempt("a1"), attempt("a2"), attempt("a3")]
        self.assertEqual(len(rank_strategies(rows)), 1)
        self.assertEqual(rank_strategies(rows)[0]["qualified_observations"], 3)
        self.assertEqual(rank_strategies(rows[:2]), [])

    def test_strategy_does_not_mix_different_statements_or_toolchains(self):
        rows = [attempt("a1", statement="x"), attempt("a2", statement="y"),
                attempt("a3", statement="z")]
        self.assertEqual(rank_strategies(rows), [])

    def test_unqualified_success_does_not_rank(self):
        rows = [attempt("a1", qualified=False), attempt("a2", qualified=False),
                attempt("a3", qualified=False)]
        self.assertEqual(rank_strategies(rows), [])

    def test_cross_domain_link_binds_proof_to_object_and_engineering_revision(self):
        import hashlib
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        links = object_view_engineering_links(
            "MathAI.Geometry.dot_comm", ["object-view:vector-dot"],
            "project:robot-arm", digest("engineering revision"), "constrains",
            digest("proof receipt"),
        )
        with tempfile.TemporaryDirectory() as directory:
            store = ProofObservatory(Path(directory) / "links.sqlite")
            stored_hash = store.record_link(links[0])
            self.assertEqual(len(stored_hash), 64)
            self.assertEqual(store.links_for_theorem("MathAI.Geometry.dot_comm")[0]["object_view_id"],
                             "object-view:vector-dot")
            store.close()

    def test_cross_domain_link_rejects_missing_revision_hash(self):
        with self.assertRaises(ValueError):
            CrossDomainLink("t", "o", "p", "bad", "supports", "0" * 64).validate()


if __name__ == "__main__":
    unittest.main()
