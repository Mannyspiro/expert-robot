import tempfile
import unittest
from pathlib import Path

from merlin.engineering_ir import EngineeringProject
from merlin.representation_graph import Frame, RepresentationGraph, identity

from merlin.proof_observatory import (
    CrossDomainLink, GoalKey, ProofAttempt, ProofObservatory,
    link_representation_frames_to_engineering_project, object_view_engineering_links,
    proof_attempt_from_qualified_receipt, rank_strategies,
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
        axiom_audit_passed=qualified,
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

    def test_representation_graph_binds_to_canonical_engineering_revision(self):
        import hashlib
        from fractions import Fraction
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        graph = RepresentationGraph([
            Frame("cartesian-3d", identity(3)),
            Frame("projective-3d", identity(3)),
        ])
        project = EngineeringProject("proof-linked-project", "mm", (), ())
        links = link_representation_frames_to_engineering_project(
            "MathAI.Geometry.frame_identity", graph,
            ["cartesian-3d", "projective-3d"], "project:proof-linked",
            project, "preserves-coordinate-invariant", digest("receipt"),
        )
        self.assertEqual(len(links), 2)
        from merlin.engineering_project_store import project_hash
        self.assertEqual(links[0].engineering_revision_sha256, project_hash(project))

    def test_representation_bridge_rejects_unknown_frame(self):
        import hashlib
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        graph = RepresentationGraph([Frame("cartesian", identity(2))])
        project = EngineeringProject("p", "mm", (), ())
        with self.assertRaises(KeyError):
            link_representation_frames_to_engineering_project(
                "t", graph, ["missing"], "p", project, "supports", digest("receipt")
            )

    def test_validated_lean_receipt_becomes_proof_observation(self):
        import hashlib
        from merlin.lean_proof_receipt import LeanProofReceipt
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        receipt = LeanProofReceipt(
            repository="Mannyspiro/expert-robot",
            commit_sha="a" * 40,
            workflow_run_id=12345,
            workflow_run_url="https://github.com/Mannyspiro/expert-robot/actions/runs/12345",
            workflow_name="Formal Qualification",
            conclusion="success",
            theorem="MathAI.Example.identity",
            theorem_compiled=True,
            axiom_audit_passed=True,
            axioms=("propext",),
            source_sha256=digest("source"),
        )
        goal = GoalKey("MathAI.Example.identity", digest("statement"), digest("assumptions"),
                       "algebra", ("cartesian-2d",))
        observation = proof_attempt_from_qualified_receipt(
            receipt, goal, ("rfl",), lean_version="4.34.0",
            mathlib_revision="locked-mathlib", import_closure_sha256=digest("imports"),
            elapsed_ms=10.0, heartbeats=20, peak_memory_bytes=4096,
            no_sorry=True, exact_target_declaration=True,
        )
        self.assertTrue(observation.qualified)
        self.assertEqual(observation.source_commit, "a" * 40)

    def test_receipt_adapter_rejects_statement_theorem_mismatch(self):
        import hashlib
        from merlin.lean_proof_receipt import LeanProofReceipt
        digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
        receipt = LeanProofReceipt(
            "Mannyspiro/expert-robot", "a" * 40, 12345,
            "https://github.com/Mannyspiro/expert-robot/actions/runs/12345",
            "Formal Qualification", "success", "MathAI.Other.theorem",
            True, True, ("propext",), digest("source"),
        )
        goal = GoalKey("MathAI.Example.identity", digest("statement"), digest("assumptions"), "algebra")
        with self.assertRaises(ValueError):
            proof_attempt_from_qualified_receipt(
                receipt, goal, ("rfl",), lean_version="4.34.0",
                mathlib_revision="locked", import_closure_sha256=digest("imports"),
                elapsed_ms=1, heartbeats=1, peak_memory_bytes=None,
                no_sorry=True, exact_target_declaration=True,
            )


if __name__ == "__main__":
    unittest.main()
