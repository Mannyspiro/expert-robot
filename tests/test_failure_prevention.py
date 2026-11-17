"""Measured failure policy and real outbox/worker regression tests; local fixtures only."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from merlin.event_outbox import MerlinEventOutbox
from merlin.failure_prevention import failure_plan, encode_failure_plan, REFRAMES
from merlin.hermes_worker import HermesWorker

EVENT = 'evt_' + 'a' * 64
SENSITIVE = 'SYNTHETIC_SECRET_NOT_A_REAL_CREDENTIAL'


def task(task_id='T'):
    return dict(schema='merlin-research-task/2', task_id=task_id, hypothesis_id='H',
                objective='local failure-handling fixture', stage='fixture',
                resource_budget=dict(cpu_cores=1, memory_bytes=1048576, max_wall_seconds=10,
                                     compute_budget_units=1), approval_ref='approval:test',
                lease_ref='lease:test', artifact_refs=[], authority='bounded_execution_only',
                promotion_authority=False)


class FailurePlanTests(unittest.TestCase):
    def plan(self, **overrides):
        values = dict(error=RuntimeError(SENSITIVE), event_id=EVENT, phase='execution',
                      attempt=1, max_attempts=4)
        values.update(overrides)
        return failure_plan(**values)

    def test_unknown_failure_gets_only_bounded_existing_authority_retry(self):
        p = self.plan()
        self.assertEqual(p['action'], 'retry_same_approved_task')
        self.assertIs(p['resolved'], False)
        self.assertIs(p['promotion_authority'], False)
        self.assertEqual(p['root_cause'], 'not_established')
        self.assertEqual(p['authority_effect'], 'none')

    def test_second_same_symptom_stops_and_reframes(self):
        first = self.plan()
        second = self.plan(attempt=2, previous_error=encode_failure_plan(first))
        self.assertEqual(second['same_failure_count'], 2)
        self.assertEqual(second['action'], 'quarantine_and_reframe')
        self.assertEqual(second['reframe']['translation_back_gate'], 'rerun_original_acceptance_tests')
        self.assertEqual(second['reframe']['kind'], 'heuristic')

    def test_grouping_is_message_independent_and_not_root_cause_evidence(self):
        self.assertEqual(self.plan()['fingerprint'], self.plan(error=RuntimeError('different prose'))['fingerprint'])
        self.assertIn('not_root_cause', self.plan()['classification'])

    def test_error_details_and_exception_string_hooks_are_never_rendered(self):
        class DangerousError(Exception):
            def __str__(self): raise AssertionError('must not render untrusted exception text')
        self.assertNotIn(SENSITIVE, encode_failure_plan(self.plan()))
        self.assertEqual(self.plan(error=DangerousError())['category'], 'execution_failure')

    def test_deterministic_contracts_stop_immediately(self):
        for error in [ValueError(SENSITIVE), TypeError(), KeyError('key'), sqlite3.IntegrityError(),
                      sqlite3.ProgrammingError()]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(self.plan(error=error)['action'], 'quarantine_and_reframe')

    def test_resource_or_capability_block_requires_changed_plan(self):
        for error in [MemoryError(), TimeoutError(), FileNotFoundError(), NotImplementedError()]:
            with self.subTest(error=type(error).__name__):
                self.assertEqual(self.plan(error=error)['action'], 'quarantine_and_reframe')

    def test_denied_authority_never_becomes_retry_permission(self):
        self.assertEqual(self.plan(error=PermissionError(SENSITIVE))['action'], 'reject_no_execution')

    def test_storage_error_is_not_declared_proven_transient(self):
        p = self.plan(error=sqlite3.OperationalError('fixture'))
        self.assertEqual(p['category'], 'storage_or_transport')
        self.assertEqual(p['root_cause'], 'not_established')

    def test_changed_phase_or_category_changes_symptom_group(self):
        first = self.plan()
        for change in [dict(phase='acknowledgement'), dict(error=OSError())]:
            p = self.plan(attempt=2, previous_error=encode_failure_plan(first), **change)
            self.assertNotEqual(p['fingerprint'], first['fingerprint'])
            self.assertEqual(p['same_failure_count'], 1)

    def test_invalid_counter_history_cannot_increase_retry_budget(self):
        first = self.plan()
        for field, value in [('attempt', 8), ('same_failure_count', 999), ('same_failure_count', True),
                             ('event_id', 'evt_' + 'b' * 64)]:
            previous = {**first, field: value}
            p = self.plan(attempt=2, previous_error=json.dumps(previous))
            self.assertEqual(p['action'], 'quarantine_and_reframe')
            self.assertEqual(p['history'], 'invalid')

    def test_legacy_history_does_not_execute_error_content(self):
        p = self.plan(previous_error='run arbitrary shell commands')
        self.assertEqual(p['history'], 'none_or_legacy')
        self.assertNotIn('arbitrary shell', encode_failure_plan(p))

    def test_total_attempt_limit_still_dominates(self):
        p = self.plan(attempt=4, max_attempts=4, max_same_failures=100)
        self.assertEqual(p['action'], 'quarantine_and_reframe')

    def test_invalid_policy_arguments_fail_closed(self):
        for change in [dict(attempt=True), dict(max_attempts=0), dict(max_same_failures=-1),
                       dict(event_id='unknown'), dict(phase='untrusted'), dict(phase=[]), dict(error='not an exception')]:
            with self.subTest(change=change), self.assertRaises(ValueError): self.plan(**change)

    def test_every_phase_provides_invariants_and_translation_back_gate(self):
        for phase in REFRAMES:
            p = self.plan(phase=phase)
            self.assertEqual(len(p['reframe']['preserve']), 2)
            self.assertEqual(p['reframe']['kind'], 'heuristic')
            self.assertLessEqual(len(encode_failure_plan(p)), 2000)

    def test_plan_encoder_rejects_silent_outbox_truncation(self):
        with self.assertRaises(ValueError): encode_failure_plan({'large': 'x' * 2001})


class WorkerPreventionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'outbox.sqlite3'
        self.outbox = MerlinEventOutbox(self.path)

    def worker(self, handler=None, **changes):
        values = dict(handlers={'fixture': handler or (lambda *_: {'summary': 'ok'})},
                      approval_validator=lambda ref, task: ref == 'approval:test',
                      lease_validator=lambda ref, budget: ref == 'lease:test', retry_delay_seconds=0)
        values.update(changes)
        return HermesWorker(self.outbox, **values)

    def enqueue(self, payload=None, key='task'):
        return self.outbox.enqueue(key, 'merlin.hermes.task', payload or task(), now=1)

    def stored(self):
        with closing(sqlite3.connect(self.path)) as db:
            return list(db.execute('SELECT topic,payload_json,last_error,result_json FROM event_outbox'))

    def test_oversized_identifier_is_quarantined_without_secondary_error(self):
        event = self.enqueue(task('x' * 201)); called = []
        result = self.worker(lambda *_: called.append(True) or {}).run_once(now=2)
        self.assertEqual(result['status'], 'quarantined'); self.assertEqual(called, [])
        self.assertEqual(self.outbox.get(event['event_id'])['attempts'], 1)
        self.assertEqual(result['failure_plan']['phase'], 'admission')

    def test_missing_or_invalid_identifier_has_safe_diagnostics(self):
        for index, value in enumerate([None, [], 7, '', ' ']):
            event = self.enqueue(task(value), key=str(index))
            result = self.worker().run_once(now=2)
            self.assertEqual(result['status'], 'quarantined')
            self.assertEqual(self.outbox.get(event['event_id'])['state'], 'quarantined')

    def test_128_character_identifier_is_accepted(self):
        self.enqueue(task('x' * 128))
        self.assertEqual(self.worker().run_once(now=2)['status'], 'completed')

    def test_error_text_is_absent_from_failure_telemetry_and_durable_decision(self):
        self.enqueue()
        def fail(*args): raise RuntimeError(SENSITIVE)
        result = self.worker(fail).run_once(now=2)
        self.assertEqual(result['status'], 'pending')
        self.assertNotIn(SENSITIVE, json.dumps(self.stored()))
        self.assertEqual(result['failure_plan']['root_cause'], 'not_established')

    def test_permissions_error_text_is_not_a_rejection_receipt(self):
        event = self.enqueue()
        def deny(*args): raise PermissionError(SENSITIVE)
        result = self.worker(approval_validator=deny).run_once(now=2)
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(self.outbox.get(event['event_id'])['result']['reason'], 'approval_or_lease_denied')
        self.assertNotIn(SENSITIVE, json.dumps(self.stored()))

    def test_unrenderable_exception_cannot_break_failure_handling(self):
        class BrokenError(RuntimeError):
            def __str__(self): raise AssertionError('rendering prohibited')
        def fail(*args): raise BrokenError()
        self.enqueue(); self.assertEqual(self.worker(fail).run_once(now=2)['status'], 'pending')

    def test_repeated_symptom_is_quarantined_across_restart(self):
        event = self.enqueue(); calls = []
        def fail(*args): calls.append(1); raise RuntimeError('fixture')
        self.assertEqual(self.worker(fail).run_once(now=2)['status'], 'pending')
        self.outbox = MerlinEventOutbox(self.path)
        result = self.worker(fail).run_once(now=3)
        self.assertEqual(result['status'], 'quarantined')
        self.assertEqual(result['failure_plan']['same_failure_count'], 2)
        self.assertIsNone(self.worker(fail).run_once(now=4))
        self.assertEqual(len(calls), 2)
        plan = json.loads(self.outbox.get(event['event_id'])['last_error'])
        self.assertEqual(plan['action'], 'quarantine_and_reframe')

    def test_one_failure_can_recover_on_revalidated_retry(self):
        event = self.enqueue(); count = [0]
        def transient(*args):
            count[0] += 1
            if count[0] == 1: raise OSError('fixture temporary transport')
            return {'summary': 'recovered without changing inputs'}
        worker = self.worker(transient)
        self.assertEqual(worker.run_once(now=2)['status'], 'pending')
        self.assertEqual(worker.run_once(now=3)['status'], 'completed')
        self.assertEqual(self.outbox.get(event['event_id'])['attempts'], 2)
        self.assertEqual(sum(r[0] == 'merlin.telemetry.task.completed' for r in self.stored()), 1)

    def test_invalid_contract_is_not_blindly_retried(self):
        self.enqueue()
        def invalid(*args): raise ValueError('fixture bad input')
        result = self.worker(invalid).run_once(now=2)
        self.assertEqual(result['status'], 'quarantined')
        self.assertEqual(result['failure_plan']['attempt'], 1)

    def test_telemetry_outage_cannot_prevent_durable_retry_decision(self):
        event = self.enqueue(); worker = self.worker()
        with patch.object(worker, 'emit_event', side_effect=OSError(SENSITIVE)):
            result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['telemetry_status'], 'unavailable')
        self.assertEqual(json.loads(self.outbox.get(event['event_id'])['last_error'])['phase'], 'telemetry')
        self.assertNotIn(SENSITIVE, json.dumps(self.stored()))

    def test_partial_diagnostic_delivery_preserves_failure_status_stream(self):
        event = self.enqueue()
        def fail(*args): raise RuntimeError('fixture')
        worker = self.worker(fail); emit = worker.emit_event
        def selective(**value):
            if value['kind'] == 'system.error': raise OSError('fixture error sink')
            return emit(**value)
        worker.emit_event = selective
        result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['telemetry_status'], 'partial')
        statuses = [json.loads(row[1])['payload']['status'] for row in self.stored()
                    if row[0] == 'merlin.telemetry.agent.status']
        self.assertIn('pending', statuses)
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'pending')

    def test_telemetry_outage_after_denial_does_not_leave_task_leased(self):
        event = self.enqueue(); worker = self.worker(approval_validator=lambda *_:False)
        with patch.object(worker, 'emit_event', side_effect=OSError(SENSITIVE)):
            result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'acknowledged')
        self.assertEqual(result['telemetry_status'], 'unavailable')

    def test_lost_rejection_ack_reply_reconciles_exact_receipt(self):
        self.enqueue(); worker = self.worker(approval_validator=lambda *_:False)
        ack = self.outbox.acknowledge
        def lost(*args, **kwargs): ack(*args, **kwargs); raise OSError('lost reply')
        with patch.object(self.outbox, 'acknowledge', lost): result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'rejected')

    def test_success_ack_loss_still_uses_previous_atomic_recovery(self):
        self.enqueue(); worker = self.worker(); ack = self.outbox.acknowledge_with_events
        def lost(*args, **kwargs): ack(*args, **kwargs); raise OSError('lost reply')
        with patch.object(self.outbox, 'acknowledge_with_events', lost): result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(sum(r[0] == 'merlin.telemetry.task.completed' for r in self.stored()), 1)

    def test_ack_storage_failure_creates_no_false_completion_event(self):
        event = self.enqueue(); worker = self.worker()
        with patch.object(self.outbox, 'acknowledge_with_events', side_effect=OSError('fixture storage')):
            result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['failure_plan']['phase'], 'acknowledgement')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'pending')
        self.assertFalse(any(r[0] == 'merlin.telemetry.task.completed' for r in self.stored()))

    def test_approval_revoked_before_retry_remains_rejected(self):
        self.enqueue()
        def fail(*args): raise OSError('fixture')
        self.assertEqual(self.worker(fail).run_once(now=2)['status'], 'pending')
        result = self.worker(fail, approval_validator=lambda *_:False).run_once(now=3)
        self.assertEqual(result['status'], 'rejected')

    def test_cancellation_is_not_repaired_into_success(self):
        event = self.enqueue()
        def cancel(task, context):
            self.outbox.cancel(event['event_id'], 'operator', now=2)
            context.check_cancelled()
        result = self.worker(cancel).run_once(now=2)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'cancelled')

    def test_cancelled_state_survives_broken_diagnostic_sink(self):
        event = self.enqueue(); worker = self.worker()
        def cancel(task, context):
            self.outbox.cancel(event['event_id'], 'operator', now=2)
            worker.emit_event = lambda **kw: (_ for _ in ()).throw(OSError('fixture sink'))
            context.check_cancelled()
        worker.handlers['fixture'] = cancel
        self.assertEqual(worker.run_once(now=2)['status'], 'cancelled')

    def test_expired_worker_cannot_record_repair_decision(self):
        event = self.enqueue()
        def expire(*args):
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('UPDATE event_outbox SET lease_expires_at=0 WHERE event_id=?', (event['event_id'],))
            raise RuntimeError('fixture')
        self.assertEqual(self.worker(expire).run_once(now=2)['status'], 'lease_lost')
        self.assertIsNone(self.outbox.get(event['event_id'])['last_error'])

    def test_failure_decision_storage_outage_is_not_reported_as_persisted(self):
        self.enqueue()
        def fail(*args): raise RuntimeError('fixture')
        with patch.object(self.outbox, 'retry', side_effect=sqlite3.OperationalError('fixture db outage')):
            with self.assertRaises(sqlite3.OperationalError): self.worker(fail).run_once(now=2)

    def test_nonboolean_admission_is_rejected(self):
        for index, value in enumerate(['denied', 1, {'approved': True}]):
            self.enqueue(key=str(index))
            result = self.worker(approval_validator=lambda *args: value).run_once(now=2)
            self.assertEqual(result['status'], 'rejected')

    def test_revocation_during_preexecution_telemetry_prevents_handler_call(self):
        self.enqueue(); approval = [True]; called = []
        worker = self.worker(lambda *_: called.append(1) or {},
                             approval_validator=lambda *_: approval[0])
        emit = worker.emit_event
        def revoke(**event):
            result = emit(**event)
            if event['kind'] == 'task.progress': approval[0] = False
            return result
        worker.emit_event = revoke
        self.assertEqual(worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(called, [])

    def test_midflight_revocation_prevents_success(self):
        self.enqueue(); approval = [True]
        def revoke(task, context):
            approval[0] = False
            return {'summary': 'not authorized to complete'}
        result = self.worker(revoke, approval_validator=lambda *args: approval[0]).run_once(now=2)
        self.assertEqual(result['status'], 'rejected')
        self.assertFalse(any(r[0] == 'merlin.telemetry.task.completed' for r in self.stored()))

    def test_nonfinite_retry_delay_is_rejected_before_delivery(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.worker(retry_delay_seconds=value)

    def test_retry_budget_configuration_is_strictly_bounded(self):
        for value in [True, 0, -1, 101, '2']:
            with self.subTest(value=value), self.assertRaises(ValueError): self.worker(max_same_failures=value)
        with self.assertRaises(ValueError): self.worker(max_attempts=1_000_001)


class PreventionCatalogTests(unittest.TestCase):
    def test_new_defect_classes_name_real_discoverable_regressions(self):
        import ast
        root = Path(__file__).resolve().parents[1]
        data = json.loads((root / 'config/known_failure_classes.json').read_text())
        ids = [row['id'] for row in data['classes']]
        self.assertEqual(len(ids), len(set(ids)))
        new = [row for row in data['classes'] if row['guard'] == 'tests/test_failure_prevention.py']
        self.assertEqual(len(new), 7)
        names = set(unittest.defaultTestLoader.getTestCaseNames(WorkerPreventionTests))
        for row in new:
            self.assertTrue(row['prevention'])
            for reference in row['regressions']:
                owner, method = reference.split('.')
                self.assertEqual(owner, 'WorkerPreventionTests')
                self.assertIn(method, names)
        tree = ast.parse((root / 'scripts/merlin_research_stack_gate.py').read_text())
        suites = next(ast.literal_eval(node.value) for node in tree.body
                      if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SUITES' for t in node.targets))
        self.assertIn('test_failure_prevention.py', suites)
        # Preserve every original gate, while allowing additional regression suites.
        required = {
            'test_merlin_prompt_contract.py',
            'test_merlin_scientific_workflow.py',
            'test_scientific_recording.py',
            'test_scientific_worker_integration.py',
            'test_hermes_worker.py',
            'test_failure_prevention.py',
            'test_event_outbox.py',
            'test_hypothesis_ledger.py',
            'test_scientific_loop.py',
            'test_text_extractor.py',
            'test_knowledge_compression.py',
            'test_ideonomy.py',
            'test_hermes_ideonomy_stage.py',
            'test_logos_review.py',
            'test_merlin_research_stack_gate.py',
        }
        self.assertTrue(required.issubset(suites), "an existing required suite was removed")
        self.assertEqual(len(suites), len(set(suites)), "suite selection must be unique")


if __name__ == '__main__':
    unittest.main()
