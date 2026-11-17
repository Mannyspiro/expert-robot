"""Real canonical registry/journal integration; no live provider or verifier."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from merlin.hermes_stage_journal import StageJournalConflict
from merlin.project_registry import MerlinRegistry
from merlin.scientific_recording import (
    MEDIA_TYPE, PREFIX, SCHEMA, STAGE, ScientificRecordingStore,
    build_scientific_recording_handler,
)

REPOSITORY = "Mannyspiro/expert-robot"
COMMIT = "b0cfc03e693d565f4f71b923ad237d496b054b6c"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


class ScientificRecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = MerlinRegistry(Path(self.temp.name) / "registry")
        self.registry.register_project("merlin", "Merlin")
        self.store = self.new_store()
        self.handler = self.new_handler()
        self.counter = 0
        self.raw = self.raw_artifact("raw/data.json", b'{"latency":10}')
        self.log = self.raw_artifact("raw/run.log", b"fixture experiment log: completed")
        self.observation = {
            "observation_id": "O-1", "question": "What is the fixture latency?",
            "method": "deterministic fixture measurement", "measurements": {"latency": 10.0},
            "units": {"latency": "ms"}, "uncertainty": {"latency": 0.1},
            "conditions": {"environment": "unit-test fixture, not production"},
            "source_refs": ["sha256:" + self.raw["sha256"]],
            "observed_at": "2026-11-17T00:00:00Z", "artifact_sha256": self.raw["sha256"],
        }
        self.plan_data = {
            "plan_id": "P-1", "objective": "Test the fixture latency prediction",
            "assumptions": ["The fixture is deterministic."],
            "alternatives": ["latency is near 10 ms", "latency changes under load"],
            "acceptance_criteria": ["Report the measured interval without promotion."],
            "falsifiers": ["The measured interval excludes the predicted range."],
            "next_actions": ["Register predictions before recording an outcome."],
        }
        self.prediction_data = {"experiment_id": "X-1",
            "predictions": [{"metric": "latency", "expected": 10.0, "tolerance": 0.5, "unit": "ms"}],
            "falsifiers": {"latency": "Measured interval lies outside 9.5 to 10.5 ms."}}

    def new_store(self, **overrides):
        config = dict(project_id="merlin", hypothesis_id="H-1", episode_id="E-1",
                      repository=REPOSITORY, commit_sha=COMMIT)
        config.update(overrides)
        return ScientificRecordingStore(self.registry, **config)

    def new_handler(self, admission=lambda task, context: True, **overrides):
        config = dict(registry=self.registry, project_id="merlin", repository=REPOSITORY,
                      commit_sha=COMMIT, admission_validator=admission)
        config.update(overrides)
        return build_scientific_recording_handler(**config)

    def raw_artifact(self, path, content):
        self.registry.put_artifact("merlin", path, content, "application/octet-stream")
        return self.registry.artifact_ref("merlin", path)

    def task(self, operation, data, refs):
        self.counter += 1
        task_id = "T-" + str(self.counter)
        budget = {"cpu_cores": 1, "memory_bytes": 64 * 1048576,
                  "max_wall_seconds": 10, "compute_budget_units": 1}
        task = {"schema": "merlin-research-task/2", "stage": STAGE, "task_id": task_id,
                "hypothesis_id": "H-1", "objective": "Record a scientific workflow artifact.",
                "promotion_authority": False, "authority": "bounded_execution_only",
                "approval_ref": "approval:test-fixture", "lease_ref": "lease:test-fixture",
                "resource_budget": budget, "artifact_refs": refs,
                "experiment_spec": {"episode_id": "E-1", "operation": operation, "data": data}}
        context = SimpleNamespace(task_id=task_id, hypothesis_id="H-1", idempotency_key=task_id,
            approval_ref=task["approval_ref"], lease_ref=task["lease_ref"], resource_budget=budget,
            artifact_refs=tuple(refs), check_cancelled=lambda: None)
        return task, context

    def record(self, operation, data, refs):
        task, context = self.task(operation, deepcopy(data), deepcopy(refs))
        result = self.handler(task, context)
        self.assertEqual(result["evidence_refs"], [])
        self.assertIs(result["promotion_authority"], False)
        self.assertIs(result["qualification"], False)
        self.assertEqual(result["verification_status"], "unverified")
        return result["artifact_refs"][0]

    def chain(self):
        observation = self.record("observation", self.observation, [self.raw])
        plan = self.record("plan", self.plan_data, [observation])
        predictions = self.record("prediction_set", self.prediction_data, [plan])
        return observation, plan, predictions

    def outcome(self, predictions, observation, **changes):
        data = dict(run_id="R-" + str(self.counter + 1), status="completed", reason="Fixture completed.", observation_count=1)
        data.update(changes)
        refs = [predictions] + ([observation] if data["observation_count"] else []) + [self.log]
        return self.record("outcome", data, refs)

    def revision(self, plan, outcomes, **changes):
        data = {"changes": ["Retain the measured result; investigate load next."],
                "next_actions": ["Preregister a bounded load experiment."]}
        data.update(changes)
        return self.record("plan_revision", data, [plan, *outcomes])

    def test_complete_recording_path_preserves_parent_and_originals(self):
        observation, plan, predictions = self.chain()
        original = self.registry.read_artifact_ref(plan)["content"]
        outcome = self.outcome(predictions, observation)
        revised = self.revision(plan, [outcome])
        record = self.store.read(revised)
        self.assertEqual(record["payload"]["version"], 2)
        self.assertEqual(record["payload"]["parent_plan_ref"], plan)
        self.assertEqual(record["payload"]["update"]["parent_plan_version"], 1)
        self.assertEqual(self.registry.read_artifact_ref(plan)["content"], original)
        self.assertEqual(self.registry.read_artifact_ref(self.raw)["content"], b'{"latency":10}')
        self.assertEqual(self.store.read(outcome)["payload"]["assessments"][0]["overall"], "consistent_with_prediction")
        for ref in (observation, plan, predictions, outcome, revised):
            self.assertEqual(len(self.registry.artifact_history("merlin", ref["logical_path"])), 1)

    def test_completed_replay_after_database_reopen_is_identical(self):
        task, context = self.task("observation", self.observation, [self.raw])
        first = self.handler(task, context)
        before = self.registry.inventory("merlin")
        self.registry = MerlinRegistry(self.registry.root)
        replay = self.new_handler()(task, context)
        self.assertEqual(first, replay)
        self.assertEqual(before, self.registry.inventory("merlin"))

    def test_changed_input_and_objective_rejected_for_same_task(self):
        task, context = self.task("observation", self.observation, [self.raw])
        self.handler(task, context)
        for change in ("objective", "measurement"):
            changed = deepcopy(task)
            if change == "objective":
                changed["objective"] = "Different immutable objective"
            else:
                changed["experiment_spec"]["data"]["measurements"]["latency"] = 12
            with self.subTest(change=change), self.assertRaises(StageJournalConflict):
                self.handler(changed, context)

    def test_changed_runtime_commit_rejected_on_replay(self):
        task, context = self.task("observation", self.observation, [self.raw])
        self.handler(task, context)
        with self.assertRaises(StageJournalConflict):
            self.new_handler(commit_sha="a" * 40)(task, context)

    def test_checkpoint_recovers_after_registry_write_failure(self):
        task, context = self.task("observation", self.observation, [self.raw])
        with patch.object(self.registry, "put_artifact", side_effect=RuntimeError("injected write failure")):
            with self.assertRaises(RuntimeError):
                self.handler(task, context)
        with sqlite3.connect(self.registry.root / "hermes-stage-journal.sqlite3") as db:
            self.assertEqual({row[0] for row in db.execute("SELECT state FROM hermes_stage_runs")}, {"generated"})
        result = self.new_handler()(task, context)
        self.assertEqual(result, self.new_handler()(task, context))

    def test_recovery_after_persistence_before_completion_does_not_duplicate(self):
        task, context = self.task("observation", self.observation, [self.raw])
        with patch("merlin.scientific_recording.HermesStageJournal.complete", side_effect=RuntimeError("injected checkpoint failure")):
            with self.assertRaises(RuntimeError):
                self.handler(task, context)
        before = self.registry.inventory("merlin")
        self.new_handler()(task, context)
        self.assertEqual(before, self.registry.inventory("merlin"))

    def test_completed_replay_rechecks_raw_source_integrity(self):
        task, context = self.task("observation", self.observation, [self.raw])
        self.handler(task, context)
        path = self.registry.blobs / self.raw["sha256"][:2] / self.raw["sha256"][2:]
        path.write_bytes(b"corruption")
        with self.assertRaises(RuntimeError):
            self.new_handler()(task, context)

    def test_missing_observation_fields_fail_before_journal_advancement(self):
        for field in ("units", "uncertainty", "conditions", "source_refs", "artifact_sha256", "observed_at"):
            data = deepcopy(self.observation); data.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.record("observation", data, [self.raw])

    def test_invalid_numeric_measurements_and_intervals_rejected(self):
        for value in (True, float("nan"), float("inf"), "10"):
            data = deepcopy(self.observation); data["measurements"]["latency"] = value
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.record("observation", data, [self.raw])
        data = deepcopy(self.observation)
        data["measurements"]["latency"] = 1e308; data["uncertainty"]["latency"] = 1e308
        with self.assertRaises(ValueError):
            self.record("observation", data, [self.raw])

    def test_unit_and_uncertainty_keys_must_match_measurements(self):
        data = deepcopy(self.observation); data["units"]["extra"] = "s"
        with self.assertRaises(ValueError):
            self.record("observation", data, [self.raw])

    def test_observation_cannot_use_unrelated_digest(self):
        for field in ("source_refs", "artifact_sha256"):
            data = deepcopy(self.observation)
            data[field] = ["sha256:" + "0" * 64] if field == "source_refs" else "0" * 64
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.record("observation", data, [self.raw])

    def test_plan_requires_observations_and_alternatives(self):
        with self.assertRaises(ValueError):
            self.record("plan", self.plan_data, [self.raw])
        observation = self.record("observation", self.observation, [self.raw])
        data = deepcopy(self.plan_data); data["alternatives"] = ["only favored hypothesis"]
        with self.assertRaises(ValueError):
            self.record("plan", data, [observation])

    def test_predictions_require_parent_falsifiers_and_unique_metrics(self):
        observation, plan, _ = self.chain()
        with self.assertRaises(ValueError):
            self.record("prediction_set", self.prediction_data, [observation])
        for key, value in (("falsifiers", {}), ("predictions", []),
                           ("predictions", self.prediction_data["predictions"] * 2)):
            data = deepcopy(self.prediction_data); data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.record("prediction_set", data, [plan])

    def test_invalid_prediction_rejected_even_for_unobserved_metric(self):
        _, plan, _ = self.chain()
        data = deepcopy(self.prediction_data)
        data["predictions"][0].update(metric="never_observed", tolerance=-1)
        data["falsifiers"] = {"never_observed": "Measure a disagreement."}
        with self.assertRaises(ValueError):
            self.record("prediction_set", data, [plan])

    def test_outcome_cannot_advance_without_prediction_and_logs(self):
        observation, plan, predictions = self.chain()
        data = {"run_id": "R-direct", "status": "completed", "reason": "test", "observation_count": 1}
        for refs in ([plan, observation, self.log], [predictions, observation], [predictions, observation, plan]):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                self.record("outcome", data, refs)

    def test_failed_and_not_run_results_remain_queryable_but_cannot_fake_measurements(self):
        observation, plan, predictions = self.chain()
        for status in ("failed", "not_run"):
            ref = self.outcome(predictions, observation, status=status, observation_count=0)
            self.assertEqual(self.store.read(ref)["payload"]["status"], status)
            with self.assertRaises(ValueError):
                self.revision(plan, [ref])
        with self.assertRaises(ValueError):
            self.outcome(predictions, observation, status="not_run", observation_count=1)

    def test_inconclusive_and_negative_outcomes_are_retained(self):
        observation, plan, predictions = self.chain()
        data = deepcopy(self.observation); data["observation_id"] = "O-negative"; data["measurements"]["latency"] = 20
        negative = self.record("observation", data, [self.raw])
        result = self.outcome(predictions, negative)
        self.assertEqual(self.store.read(result)["payload"]["assessments"][0]["overall"], "contradicted")
        data["observation_id"] = "O-uncertain"; data["measurements"]["latency"] = 10; data["uncertainty"]["latency"] = 2
        uncertain = self.record("observation", data, [self.raw])
        result2 = self.outcome(predictions, uncertain, status="inconclusive")
        self.assertEqual(self.store.read(result2)["payload"]["assessments"][0]["overall"], "inconclusive")
        revised = self.revision(plan, [result, result2])
        self.assertEqual(len(self.store.read(revised)["payload"]["outcome_refs"]), 2)

    def test_unobserved_or_incomparable_units_stay_inconclusive(self):
        observation, plan, predictions = self.chain()
        for metric, unit in (("other", "ms"), ("latency", "s")):
            data = deepcopy(self.prediction_data)
            data["experiment_id"] = "X-" + metric + "-" + unit
            data["predictions"][0].update(metric=metric, unit=unit)
            data["falsifiers"] = {metric: "Disagreement under the registered test."}
            ref = self.record("prediction_set", data, [plan])
            outcome = self.outcome(ref, observation)
            self.assertEqual(self.store.read(outcome)["payload"]["assessments"][0]["overall"], "inconclusive")

    def test_revision_rejects_wrong_parent_and_cannot_change_acceptance_threshold(self):
        observation, plan, predictions = self.chain()
        outcome = self.outcome(predictions, observation)
        other = deepcopy(self.plan_data); other["plan_id"] = "P-2"
        other_plan = self.record("plan", other, [observation])
        with self.assertRaises(ValueError):
            self.revision(other_plan, [outcome])
        with self.assertRaises(ValueError):
            self.revision(plan, [outcome], acceptance_criteria=["weakened threshold"])

    def test_divergent_proposals_have_distinct_refs_and_preserve_same_parent(self):
        observation, plan, predictions = self.chain()
        outcome = self.outcome(predictions, observation)
        first = self.revision(plan, [outcome])
        second = self.revision(plan, [outcome], next_actions=["Test a different model next."])
        self.assertNotEqual(first, second)
        self.assertEqual(self.store.read(first)["payload"]["parent_plan_ref"], self.store.read(second)["payload"]["parent_plan_ref"])

    def test_episode_hypothesis_and_project_scopes_are_enforced(self):
        ref = self.record("observation", self.observation, [self.raw])
        for scope in ({"episode_id": "E-2"}, {"hypothesis_id": "H-2"}, {"project_id": "other"}):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.new_store(**scope).read(ref)

    def test_historical_record_survives_code_revision_without_rewriting(self):
        ref = self.record("observation", self.observation, [self.raw])
        self.assertEqual(self.new_store(commit_sha="a" * 40).read(ref)["source_commit"], COMMIT)

    def test_same_bytes_at_other_paths_are_distinct_input_identities(self):
        other = self.raw_artifact("raw/other.json", b'{"latency":10}')
        first = self.record("observation", self.observation, [self.raw])
        other_data = {**self.observation, "observation_id": "O-distinct-path"}
        second = self.record("observation", other_data, [other])
        self.assertEqual(self.raw["sha256"], other["sha256"])
        self.assertNotEqual(first, second)

    def test_stale_raw_version_does_not_resolve_to_latest(self):
        self.registry.put_artifact("merlin", "raw/data.json", b'{"latency":20}')
        ref = self.record("observation", self.observation, [self.raw])
        self.assertEqual(self.store.read(ref)["input_refs"], [self.raw])
        self.assertEqual(self.registry.read_artifact_ref(self.raw)["content"], b'{"latency":10}')

    def test_canonical_sqlite_versions_are_append_only(self):
        ref = self.record("observation", self.observation, [self.raw])
        with sqlite3.connect(self.registry.db_path) as db:
            for statement in ("UPDATE artifact_versions SET digest=digest", "DELETE FROM artifact_versions"):
                with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    db.execute(statement)
        self.store.read(ref)

    def test_prepared_payload_cannot_be_tampered(self):
        prepared = self.store.prepare("observation", self.observation, [self.raw])
        prepared["payload"]["measurements"]["latency"] = 99
        with self.assertRaises(ValueError):
            self.store.persist(prepared)

    def test_coherently_rehashed_false_derived_payload_rejected(self):
        record = self.store.prepare("observation", self.observation, [self.raw])
        record["payload"]["measurements"]["latency"] = 99
        content = canonical(record); digest = hashlib.sha256(content).hexdigest()
        path = PREFIX + digest + ".json"
        self.registry.put_artifact("merlin", path, content, MEDIA_TYPE,
                                   provenance=self.store._provenance(record, digest))
        ref = self.registry.artifact_ref("merlin", path)
        with self.assertRaisesRegex(ValueError, "derived payload mismatch"):
            self.store.read(ref)

    def test_missing_or_forged_provenance_rejected(self):
        record = self.store.prepare("observation", self.observation, [self.raw])
        content = canonical(record); digest = hashlib.sha256(content).hexdigest()
        path = PREFIX + digest + ".json"
        self.registry.put_artifact("merlin", path, content, MEDIA_TYPE)
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            self.store.read(self.registry.artifact_ref("merlin", path))

    def test_authority_claims_are_rejected_not_stripped(self):
        data = deepcopy(self.observation); data["verified"] = True
        with self.assertRaises(ValueError):
            self.record("observation", data, [self.raw])
        task, context = self.task("observation", self.observation, [self.raw])
        task["promotion_authority"] = True
        with self.assertRaises(PermissionError):
            self.handler(task, context)

    def test_admission_requires_literal_true(self):
        task, context = self.task("observation", self.observation, [self.raw])
        for value in (False, None, 1, "approved"):
            with self.subTest(value=value), self.assertRaises(PermissionError):
                self.new_handler(admission=lambda task, context, v=value: v)(task, context)

    def test_context_identity_approval_lease_refs_and_budget_are_bound(self):
        for field, value in (("task_id", "other"), ("hypothesis_id", "other"),
                             ("approval_ref", "other"), ("lease_ref", "other"),
                             ("artifact_refs", []), ("resource_budget", {})):
            task, context = self.task("observation", self.observation, [self.raw])
            task[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.handler(task, context)

    def test_cancellation_before_recording_preserves_empty_stage_journal(self):
        task, context = self.task("observation", self.observation, [self.raw])
        context.check_cancelled = lambda: (_ for _ in ()).throw(RuntimeError("cancelled"))
        with self.assertRaises(RuntimeError):
            self.handler(task, context)
        with sqlite3.connect(self.registry.root / "hermes-stage-journal.sqlite3") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM hermes_stage_runs").fetchone()[0], 0)

    def test_duplicate_refs_and_unknown_operations_rejected(self):
        with self.assertRaises(ValueError):
            self.record("observation", self.observation, [self.raw, self.raw])
        with self.assertRaises(ValueError):
            self.record("qualify", {}, [self.raw])

    def test_aggregate_input_and_lineage_budgets_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "aggregate input"):
            self.new_store(max_input_bytes=1).prepare("observation", self.observation, [self.raw])
        observation, plan, predictions = self.chain()
        with patch("merlin.scientific_recording.MAX_LINEAGE_RECORDS", 1):
            with self.assertRaisesRegex(ValueError, "lineage inspection"):
                self.store.read(predictions)

    def test_source_size_and_symlink_admission_precedes_full_registry_read(self):
        oversized = self.raw_artifact("raw/oversized", b"x" * (1048576 + 1))
        with patch.object(self.registry, "read_artifact_ref", side_effect=AssertionError("must not read")):
            with self.assertRaises(ValueError):
                self.store.prepare("observation", self.observation, [oversized])
        blob = self.registry.blobs / self.raw["sha256"][:2] / self.raw["sha256"][2:]
        target = Path(self.temp.name) / "sentinel"; target.write_bytes(blob.read_bytes())
        blob.unlink(); blob.symlink_to(target)
        with self.assertRaises(ValueError):
            self.store.prepare("observation", self.observation, [self.raw])

    def test_tampered_checkpoint_is_rejected_on_replay(self):
        task, context = self.task("observation", self.observation, [self.raw])
        self.handler(task, context)
        with sqlite3.connect(self.registry.root / "hermes-stage-journal.sqlite3") as db:
            db.execute("UPDATE hermes_stage_runs SET candidate_set_json='{}'")
        with self.assertRaises(StageJournalConflict):
            self.new_handler()(task, context)

    def test_result_tampering_is_not_accepted_as_completed_replay(self):
        task, context = self.task("observation", self.observation, [self.raw])
        self.handler(task, context)
        with sqlite3.connect(self.registry.root / "hermes-stage-journal.sqlite3") as db:
            db.execute("UPDATE hermes_stage_runs SET result_json='{}'")
        with self.assertRaises(StageJournalConflict):
            self.new_handler()(task, context)

    def test_observation_id_cannot_be_reused_with_changed_measurements(self):
        self.record("observation", self.observation, [self.raw])
        changed = deepcopy(self.observation); changed["measurements"]["latency"] = 11
        with self.assertRaises(StageJournalConflict):
            self.record("observation", changed, [self.raw])

    def test_plan_root_cannot_be_recreated_with_same_plan_id(self):
        observation, plan, predictions = self.chain()
        changed = deepcopy(self.plan_data); changed["objective"] = "Replace original objective."
        with self.assertRaises(StageJournalConflict):
            self.record("plan", changed, [observation])

    def test_experiment_id_prevents_post_hoc_prediction_replacement(self):
        observation, plan, predictions = self.chain()
        self.outcome(predictions, observation)
        changed = deepcopy(self.prediction_data); changed["predictions"][0]["tolerance"] = 100
        with self.assertRaises(StageJournalConflict):
            self.record("prediction_set", changed, [plan])

    def test_run_id_cannot_be_reused_to_change_failure_to_completion(self):
        observation, plan, predictions = self.chain()
        self.outcome(predictions, observation, run_id="R-stable", status="failed")
        with self.assertRaises(StageJournalConflict):
            self.outcome(predictions, observation, run_id="R-stable", status="completed")

    def test_completed_stage_with_missing_checkpoint_is_rejected(self):
        task, context = self.task("observation", self.observation, [self.raw])
        self.handler(task, context)
        with sqlite3.connect(self.registry.root / "hermes-stage-journal.sqlite3") as db:
            db.execute("UPDATE hermes_stage_runs SET candidate_set_json=NULL WHERE stage=?", (STAGE,))
        with self.assertRaises(StageJournalConflict):
            self.new_handler()(task, context)


if __name__ == "__main__":
    unittest.main()
