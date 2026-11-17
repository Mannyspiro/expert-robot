"""Real worker/outbox/registry integration with explicit TEST authorization policies.

No remote provider, independent verifier, production approval service or OS sandbox.
"""
from copy import deepcopy
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from merlin.event_outbox import MerlinEventOutbox, LeaseConflict, OutboxConflict
from merlin.hermes_worker import HermesWorker, HERMES_TASK_TOPIC
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.project_registry import MerlinRegistry
from merlin.scientific_recording import (
    STAGE, PREFIX, ScientificRecordingStore, register_scientific_recording,
)

REPOSITORY = 'Mannyspiro/expert-robot'
SOURCE = '1754d4819d5b6bc0ec2dcc09bf6c2e0a98549011'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def rows(outbox):
    with closing(sqlite3.connect(outbox.path)) as db, db:
        db.row_factory = sqlite3.Row
        return [{**dict(row), 'payload': json.loads(row['payload_json'])}
                for row in db.execute('SELECT * FROM event_outbox ORDER BY created_at,event_id')]


class RecordingWorkerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = MerlinRegistry(self.root / 'registry')
        self.registry.register_project('merlin', 'Merlin integration fixture')
        self.ledger = HypothesisLedger(self.root / 'hypotheses.sqlite3')
        self.ledger.create('H-1', 'Test fixture hypothesis, not a verified claim')
        self.outbox = MerlinEventOutbox(self.root / 'outbox.sqlite3')
        self.raw = self.raw_artifact('raw/data.json', b'{"latency":10}')
        self.log = self.raw_artifact('raw/run.log', b'local test fixture log')
        self.policy = {'approval': True, 'lease': True}
        self.counter = 0
        self.observation = dict(
            observation_id='O-1', question='What is the fixture latency?',
            method='test fixture, not a production measurement', measurements={'latency': 10.0},
            units={'latency': 'ms'}, uncertainty={'latency': 0.1},
            conditions={'environment': 'unit test fixture'},
            source_refs=['sha256:' + self.raw['sha256']], observed_at='2026-11-17T00:00:00Z',
            artifact_sha256=self.raw['sha256'])
        self.plan = dict(plan_id='P-1', objective='Test fixture prediction', assumptions=['fixture only'],
                         alternatives=['latency is near 10 ms', 'latency depends on load'],
                         acceptance_criteria=['retain raw observations and uncertainty'],
                         falsifiers=['measurement outside predicted range'], next_actions=['record predictions'])
        self.predictions = dict(experiment_id='X-1', predictions=[dict(metric='latency', expected=10.0,
                                tolerance=0.5, unit='ms')], falsifiers={'latency': 'outside 9.5 to 10.5 ms'})
        self.worker = self.make_worker()

    def raw_artifact(self, path, content):
        self.registry.put_artifact('merlin', path, content)
        return self.registry.artifact_ref('merlin', path)

    def approved(self, ref, task):
        if self.policy['approval'] is not True:
            return self.policy['approval']
        return (ref == 'approval:fixture' and task['stage'] == STAGE
                and task['hypothesis_id'] == 'H-1'
                and task['experiment_spec']['episode_id'] == 'E-1')

    def leased(self, ref, budget):
        if self.policy['lease'] is not True:
            return self.policy['lease']
        return ref == 'lease:fixture' and budget['cpu_cores'] == 1 and budget['memory_bytes'] <= 64 * 1048576

    def handlers(self, **changes):
        values = dict(enabled=True, registry=self.registry, ledger=self.ledger, project_id='merlin',
                      repository=REPOSITORY, commit_sha=SOURCE,
                      approval_validator=self.approved, lease_validator=self.leased)
        values.update(changes)
        return register_scientific_recording({}, **values)

    def make_worker(self, **changes):
        values = dict(handlers=self.handlers(), approval_validator=self.approved,
                      lease_validator=self.leased, retry_delay_seconds=0, max_attempts=1,
                      artifact_ref_validator=lambda ref: self.registry.resolve_artifact_ref(ref)['verified'] is True)
        values.update(changes)
        return HermesWorker(self.outbox, **values)

    def task(self, operation='observation', data=None, refs=None):
        self.counter += 1
        return dict(schema='merlin-research-task/2', stage=STAGE, task_id='T-' + str(self.counter),
                    hypothesis_id='H-1', objective='Record fixture scientific data',
                    authority='bounded_execution_only', promotion_authority=False,
                    approval_ref='approval:fixture', lease_ref='lease:fixture',
                    resource_budget=dict(cpu_cores=1, memory_bytes=64 * 1048576,
                                         max_wall_seconds=10, compute_budget_units=1),
                    artifact_refs=deepcopy(refs if refs is not None else [self.raw]),
                    experiment_spec=dict(episode_id='E-1', operation=operation,
                                         data=deepcopy(self.observation if data is None else data)))

    def enqueue(self, task):
        return self.outbox.enqueue('research-task:' + task['task_id'], HERMES_TASK_TOPIC, task, now=1)

    def run_record(self, operation, data, refs):
        task = self.task(operation, data, refs)
        event = self.enqueue(task)
        result = self.worker.run_once(now=2)
        self.assertEqual(result['status'], 'completed', result)
        persisted = self.outbox.get(event['event_id'])
        self.assertEqual(persisted['state'], 'acknowledged')
        receipt = persisted['result']
        self.assertEqual(receipt['evidence_refs'], [])
        self.assertEqual(receipt['result']['verification_status'], 'unverified')
        self.assertIs(receipt['result']['qualification'], False)
        self.assertIs(receipt['promotion_authority'], False)
        self.assertEqual(len(receipt['output_artifact_refs']), 1)
        return receipt['output_artifact_refs'][0]

    def completed(self):
        return [r for r in rows(self.outbox) if r['topic'] == 'merlin.telemetry.task.completed']

    def store(self):
        return ScientificRecordingStore(self.registry, project_id='merlin', hypothesis_id='H-1',
                                        episode_id='E-1', repository=REPOSITORY, commit_sha=SOURCE)

    def test_full_recording_chain_through_real_worker_and_acknowledgement(self):
        obs = self.run_record('observation', self.observation, [self.raw])
        plan = self.run_record('plan', self.plan, [obs])
        before = self.registry.read_artifact_ref(plan)['content']
        pred = self.run_record('prediction_set', self.predictions, [plan])
        outcome = self.run_record('outcome', dict(run_id='R-1', status='completed', reason='fixture ran',
                                                observation_count=1), [pred, obs, self.log])
        rev = self.run_record('plan_revision', dict(changes=['retain measurement'], next_actions=['test load']),
                              [plan, outcome])
        record = self.store().read(rev)
        self.assertEqual(record['payload']['parent_plan_ref'], plan)
        self.assertEqual(record['payload']['version'], 2)
        self.assertEqual(self.registry.read_artifact_ref(plan)['content'], before)
        self.assertEqual(len(self.completed()), 5)
        self.assertEqual(self.ledger.evidence('H-1'), [])
        self.assertEqual(self.ledger.get('H-1').status, 'proposed')
        for event in self.completed():
            parent = self.outbox.get(event['payload']['payload']['task_event_id'])
            self.assertEqual(parent['state'], 'acknowledged')
            self.assertEqual(event['payload']['payload']['receipt_sha256'],
                             hashlib.sha256(canonical(parent['result']).encode()).hexdigest())

    def test_negative_and_inconclusive_outcomes_are_retained_without_promotion(self):
        obs = self.run_record('observation', self.observation, [self.raw])
        plan = self.run_record('plan', self.plan, [obs])
        pred = self.run_record('prediction_set', self.predictions, [plan])
        for status, count in [('failed', 0), ('not_run', 0), ('inconclusive', 1)]:
            ref = self.run_record('outcome', dict(run_id='R-' + status, status=status, reason='fixture ' + status,
                                 observation_count=count), [pred] + ([obs] if count else []) + [self.log])
            self.assertEqual(self.store().read(ref)['payload']['status'], status)
        self.assertEqual(self.ledger.evidence('H-1'), [])

    def test_unknown_hypothesis_is_rejected_without_scientific_artifact(self):
        task = self.task(); task['hypothesis_id'] = 'missing'
        self.enqueue(task)
        self.assertEqual(self.worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(len(self.registry.inventory('merlin')['artifacts']), 2)
        self.assertEqual(self.completed(), [])

    def test_ledger_lookup_not_only_approval_controls_unknown_hypothesis(self):
        with closing(self.ledger._connect()) as db, db:
            db.execute('DELETE FROM hypotheses WHERE hypothesis_id=?', ('H-1',))
        self.enqueue(self.task())
        self.assertEqual(self.worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(self.completed(), [])

    def test_episode_scope_denial_is_rejected(self):
        task = self.task(); task['experiment_spec']['episode_id'] = 'other'
        self.enqueue(task)
        self.assertEqual(self.worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(self.completed(), [])

    def test_cross_project_input_is_rejected(self):
        self.registry.register_project('other', 'Other fixture')
        self.registry.put_artifact('other', 'raw.json', b'{}')
        task = self.task(refs=[self.registry.artifact_ref('other', 'raw.json')])
        self.enqueue(task)
        self.assertEqual(self.worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(self.completed(), [])

    def test_truthy_nonboolean_approval_and_lease_fail_closed(self):
        for kind in ['approval', 'lease']:
            for value in ['denied', 1, {'allowed': True}]:
                with self.subTest(kind=kind, value=value):
                    self.policy = {'approval': True, 'lease': True}; self.policy[kind] = value
                    self.enqueue(self.task())
                    self.assertEqual(self.worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(self.completed(), [])

    def test_revocation_after_persistence_cannot_acknowledge_success(self):
        for key in ['approval', 'lease']:
            with self.subTest(key=key):
                self.policy = {'approval': True, 'lease': True}
                data = deepcopy(self.observation); data['observation_id'] = 'O-' + key
                self.enqueue(self.task(data=data))
                original = ScientificRecordingStore.persist
                def revoke(store, record):
                    ref = original(store, record); self.policy[key] = False; return ref
                with patch.object(ScientificRecordingStore, 'persist', revoke):
                    self.assertEqual(self.worker.run_once(now=2)['status'], 'rejected')
        self.assertEqual(self.completed(), [])
        self.assertEqual(len([a for a in self.registry.inventory('merlin')['artifacts']
                              if a['logical_path'].startswith(PREFIX)]), 2)

    def test_cancel_after_persistence_keeps_record_without_completion(self):
        event = self.enqueue(self.task()); original = ScientificRecordingStore.persist
        def cancel(store, record):
            ref = original(store, record)
            self.outbox.cancel(event['event_id'], 'operator-fixture', now=2)
            return ref
        with patch.object(ScientificRecordingStore, 'persist', cancel):
            result = self.worker.run_once(now=2)
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'cancelled')
        self.assertEqual(len(self.registry.inventory('merlin')['artifacts']), 3)
        self.assertEqual(self.completed(), [])

    def test_ack_failure_rolls_back_announcements_and_reopens_idempotently(self):
        event = self.enqueue(self.task())
        worker = self.make_worker(max_attempts=3)
        with patch.object(self.outbox, 'acknowledge_with_events', side_effect=sqlite3.OperationalError('fixture fault')):
            result = worker.run_once(now=2)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(self.completed(), [])
        before = self.registry.inventory('merlin')
        self.registry = MerlinRegistry(self.registry.root)
        self.outbox = MerlinEventOutbox(self.outbox.path)
        self.ledger = HypothesisLedger(self.ledger.database)
        result = self.make_worker(max_attempts=3).run_once(now=3)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.registry.inventory('merlin'), before)
        self.assertEqual(len(self.completed()), 1)
        self.assertIsNone(self.make_worker().run_once(now=4))
        self.assertEqual(self.outbox.get(event['event_id'])['attempts'], 2)

    def test_changed_delivery_with_same_task_id_is_quarantined(self):
        task = self.task(); self.enqueue(task)
        self.assertEqual(self.worker.run_once(now=2)['status'], 'completed')
        changed = deepcopy(task); changed['objective'] = 'changed objective'
        event = self.outbox.enqueue('another-delivery', HERMES_TASK_TOPIC, changed, now=2)
        self.assertEqual(self.worker.run_once(now=3)['status'], 'quarantined')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'quarantined')
        self.assertEqual(len(self.completed()), 1)

    def test_input_tampering_between_attempts_is_not_accepted(self):
        event = self.enqueue(self.task())
        with patch.object(self.outbox, 'acknowledge_with_events', side_effect=OSError('fixture interruption')):
            self.make_worker(max_attempts=3).run_once(now=2)
        path = self.registry.blobs / self.raw['sha256'][:2] / self.raw['sha256'][2:]
        path.write_bytes(b'changed')
        result = self.make_worker().run_once(now=3)
        self.assertEqual(result['status'], 'quarantined')
        self.assertEqual(self.completed(), [])
        self.assertIsNone(self.outbox.get(event['event_id'])['result'])

    def test_reclaimed_lease_cannot_complete_old_worker(self):
        event = self.enqueue(self.task()); original = ScientificRecordingStore.persist
        def steal(store, record):
            ref = original(store, record)
            self.outbox.recover_expired(now=1000)
            self.outbox.claim_next('replacement', topics=[HERMES_TASK_TOPIC], now=1000)
            return ref
        with patch.object(ScientificRecordingStore, 'persist', steal):
            result = self.worker.run_once(now=2)
        self.assertEqual(result['status'], 'lease_lost')
        self.assertEqual(self.outbox.get(event['event_id'])['lease_owner'], 'replacement')
        self.assertEqual(self.completed(), [])

    def test_expired_but_not_reclaimed_lease_fails_cooperative_check(self):
        event = self.enqueue(self.task()); original = ScientificRecordingStore.persist
        def expire(store, record):
            ref = original(store, record)
            with closing(sqlite3.connect(self.outbox.path)) as db, db:
                db.execute('UPDATE event_outbox SET lease_expires_at=0 WHERE event_id=?', (event['event_id'],))
            return ref
        with patch.object(ScientificRecordingStore, 'persist', expire):
            result = self.worker.run_once(now=2)
        self.assertEqual(result['status'], 'lease_lost')
        self.assertEqual(self.completed(), [])

    def test_lost_reply_after_atomic_ack_reads_committed_receipt(self):
        event = self.enqueue(self.task()); original = self.outbox.acknowledge_with_events
        def lost_reply(*args, **kwargs):
            original(*args, **kwargs); raise OSError('fixture lost reply after COMMIT')
        with patch.object(self.outbox, 'acknowledge_with_events', lost_reply):
            result = self.worker.run_once(now=2)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'acknowledged')
        self.assertEqual(len(self.completed()), 1)

    def test_actual_child_process_exit_after_record_persistence_recovers(self):
        event = self.enqueue(self.task())
        child = r'''
import os, sys
from pathlib import Path
from merlin.event_outbox import MerlinEventOutbox
from merlin.hermes_worker import HermesWorker
from merlin.project_registry import MerlinRegistry
from merlin.hypothesis_ledger import HypothesisLedger
from merlin.scientific_recording import register_scientific_recording
root = Path(sys.argv[1])
registry = MerlinRegistry(root / 'registry')
ledger = HypothesisLedger(root / 'hypotheses.sqlite3')
outbox = MerlinEventOutbox(root / 'outbox.sqlite3')
approve = lambda ref, task: ref == 'approval:fixture' and task['hypothesis_id'] == 'H-1'
lease = lambda ref, budget: ref == 'lease:fixture' and budget['cpu_cores'] == 1
handlers = register_scientific_recording({}, enabled=True, registry=registry, ledger=ledger,
    project_id='merlin', repository='Mannyspiro/expert-robot',
    commit_sha='1754d4819d5b6bc0ec2dcc09bf6c2e0a98549011',
    approval_validator=approve, lease_validator=lease)
# Deliberately terminate the interpreter after the handler completed, before ACK.
outbox.acknowledge_with_events = lambda *a, **k: os._exit(23)
worker = HermesWorker(outbox, handlers=handlers, approval_validator=approve,
    lease_validator=lease, lease_seconds=1, max_attempts=3,
    artifact_ref_validator=lambda ref: registry.resolve_artifact_ref(ref)['verified'] is True)
worker.run_once()
'''
        python_path = str(Path(__file__).resolve().parents[1] / 'python')
        result = subprocess.run([sys.executable, '-c', child, str(self.root)],
                                env={'PATH': os.defpath, 'PYTHONPATH': python_path},
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 23, result.stderr.decode())
        self.assertEqual(self.outbox.get(event['event_id'])['state'], 'leased')
        self.assertEqual(self.completed(), [])
        before = self.registry.inventory('merlin')
        future = time.time() + 10
        self.outbox.recover_expired(now=future)
        self.outbox = MerlinEventOutbox(self.outbox.path)
        self.assertEqual(self.make_worker(max_attempts=3).run_once(now=future + 1)['status'], 'completed')
        self.assertEqual(self.registry.inventory('merlin'), before)
        self.assertEqual(len(self.completed()), 1)

    def test_registration_is_explicit_nonmutating_and_rejects_replacement(self):
        self.assertEqual(self.handlers(enabled=False), {})
        for value in [1, 'true', None]:
            with self.subTest(enabled=value), self.assertRaises(ValueError):
                self.handlers(enabled=value)
        existing = {STAGE: lambda *args: {}}
        with self.assertRaises(ValueError):
            register_scientific_recording(existing, enabled=True, registry=self.registry, ledger=self.ledger,
                project_id='merlin', repository=REPOSITORY, commit_sha=SOURCE,
                approval_validator=self.approved, lease_validator=self.leased)
        self.assertEqual(set(existing), {STAGE})

    def test_missing_policy_or_noncanonical_stores_cannot_register(self):
        for change in [dict(approval_validator=None), dict(lease_validator=None),
                       dict(ledger=object()), dict(registry=object())]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.handlers(**change)

    def test_missing_prediction_or_falsifier_blocks_worker_transition(self):
        obs = self.run_record('observation', self.observation, [self.raw])
        plan = self.run_record('plan', self.plan, [obs])
        malformed = deepcopy(self.predictions); malformed['falsifiers'] = {}
        self.enqueue(self.task('prediction_set', malformed, [plan]))
        self.assertEqual(self.worker.run_once(now=2)['status'], 'quarantined')
        self.enqueue(self.task('outcome', dict(run_id='invalid', status='completed', reason='fixture',
                                               observation_count=1), [plan, obs, self.log]))
        self.assertEqual(self.worker.run_once(now=2)['status'], 'quarantined')
        self.assertEqual(len(self.completed()), 2)

    def test_ledger_connections_close_even_on_missing_hypothesis(self):
        real = sqlite3.connect
        opened = []
        def tracked(*args, **kwargs):
            connection = real(*args, **kwargs); opened.append(connection); return connection
        with patch('merlin.hypothesis_ledger.sqlite3.connect', tracked):
            self.ledger.get('H-1')
            with self.assertRaises(KeyError): self.ledger.get('missing')
            self.ledger.evidence('H-1')
            self.ledger.list_hypotheses()
            self.ledger.create('H-2', 'fixture second hypothesis')
        self.assertGreaterEqual(len(opened), 6)
        for connection in opened:
            with self.assertRaises(sqlite3.ProgrammingError): connection.execute('SELECT 1')

    def test_mutating_handler_cannot_change_admitted_task_receipt(self):
        task = self.task(); event = self.enqueue(task)
        def mutate(value, context):
            value['objective'] = 'mutated after admission'
            return {'summary': 'not a scientific recording'}
        self.worker.handlers[STAGE] = mutate
        self.assertEqual(self.worker.run_once(now=2)['status'], 'quarantined')
        self.assertEqual(self.outbox.get(event['event_id'])['payload'], task)
        self.assertEqual(self.completed(), [])

    def test_truthy_registry_result_is_not_integrity_validation(self):
        self.enqueue(self.task())
        self.worker.artifact_ref_validator = lambda ref: 'verified'
        self.assertEqual(self.worker.run_once(now=2)['status'], 'quarantined')
        self.assertEqual(self.completed(), [])

    def test_lost_reply_compares_canonical_receipt_not_python_container_type(self):
        self.enqueue(self.task())
        self.worker.handlers[STAGE] = lambda *args: {'fixture_values': (1, 2)}
        original = self.outbox.acknowledge_with_events
        def lost_reply(*args, **kwargs):
            original(*args, **kwargs); raise OSError('lost reply')
        with patch.object(self.outbox, 'acknowledge_with_events', lost_reply):
            result = self.worker.run_once(now=2)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['receipt']['result']['fixture_values'], [1, 2])
        self.assertEqual(len(self.completed()), 1)

    def test_default_runtime_wiring_is_static_only_not_full_runtime_execution(self):
        import ast
        path = Path(__file__).resolve().parents[1] / 'python/merlin/hermes_runtime.py'
        tree = ast.parse(path.read_text(), feature_version=(3, 11))
        factory = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_merlin_hermes_runtime')
        defaults = dict(zip([a.arg for a in factory.args.kwonlyargs], factory.args.kw_defaults))
        self.assertIs(ast.literal_eval(defaults['include_scientific_recording']), False)
        calls = [n for n in ast.walk(factory) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'register_scientific_recording']
        self.assertEqual(len(calls), 1)
        self.assertEqual(next(k.value.id for k in calls[0].keywords if k.arg == 'enabled'),
                         'include_scientific_recording')


class AtomicCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.outbox = MerlinEventOutbox(Path(self.temp.name) / 'outbox.sqlite3')
        self.event = self.outbox.enqueue('task:key', 'merlin.hermes.task', {'task_id': 'T'}, now=1)
        self.lease = self.outbox.claim_next('worker', now=2, lease_seconds=20)
        self.result = {'status': 'completed', 'promotion_authority': False}
        self.events = [dict(idempotency_key='completion:one', topic='merlin.telemetry.task.completed', payload={'n': 1}),
                       dict(idempotency_key='completion:two', topic='merlin.telemetry.agent.status', payload={'n': 2})]

    def ack(self, **overrides):
        args = dict(result=self.result, events=self.events, now=3); args.update(overrides)
        return self.outbox.acknowledge_with_events(self.event['event_id'], 'worker',
                                                  self.lease['lease_token'], **args)

    def test_atomic_commit_and_exact_replay(self):
        first = self.ack(); self.assertEqual(first['state'], 'acknowledged')
        self.outbox = MerlinEventOutbox(self.outbox.path)
        self.assertEqual(self.ack(), first)
        self.assertEqual(len(rows(self.outbox)), 3)

    def test_changed_receipt_or_events_or_new_event_rejected_on_replay(self):
        self.ack()
        for args in [dict(result={'status': 'different'}),
                     dict(events=[{**self.events[0], 'payload': {'n': 3}}]),
                     dict(events=[{**self.events[0], 'idempotency_key': 'new'}])]:
            with self.subTest(args=args), self.assertRaises(OutboxConflict):
                self.ack(**args)
        self.assertEqual(len(rows(self.outbox)), 3)

    def test_second_event_failure_rolls_back_first_and_ack(self):
        original = self.outbox.enqueue_in_transaction
        def fail(db, key, *args, **kwargs):
            if key == 'completion:two': raise sqlite3.OperationalError('fixture disk failure')
            return original(db, key, *args, **kwargs)
        with patch.object(self.outbox, 'enqueue_in_transaction', fail), self.assertRaises(sqlite3.OperationalError):
            self.ack()
        current = self.outbox.get(self.event['event_id'])
        self.assertEqual(current['state'], 'leased'); self.assertIsNone(current['result'])
        self.assertEqual(len(rows(self.outbox)), 1)

    def test_receipt_update_failure_rolls_back_both_announcements(self):
        with closing(sqlite3.connect(self.outbox.path)) as db, db:
            db.execute("CREATE TRIGGER fail_ack BEFORE UPDATE ON event_outbox WHEN NEW.state='acknowledged' BEGIN SELECT RAISE(ABORT, 'fixture fault'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.ack()
        self.assertEqual(len(rows(self.outbox)), 1)
        self.assertEqual(self.outbox.get(self.event['event_id'])['state'], 'leased')

    def test_wrong_or_expired_lease_never_publishes(self):
        with self.assertRaises(LeaseConflict):
            self.outbox.acknowledge_with_events(self.event['event_id'], 'wrong-worker', self.lease['lease_token'],
                                              result=self.result, events=self.events, now=3)
        with self.assertRaises(LeaseConflict): self.ack(now=23)
        self.assertEqual(len(rows(self.outbox)), 1)

    def test_expiry_during_event_insert_rolls_back(self):
        with patch('merlin.event_outbox.time.time', side_effect=[3, 23]):
            with self.assertRaises(LeaseConflict): self.ack(now=None)
        self.assertEqual(len(rows(self.outbox)), 1)

    def test_cancel_wins_before_ack(self):
        self.outbox.cancel(self.event['event_id'], 'operator', now=3)
        with self.assertRaises(LeaseConflict): self.ack()
        self.assertEqual(len(rows(self.outbox)), 1)

    def test_completion_conflict_rolls_back_ack(self):
        self.outbox.enqueue('completion:two', self.events[1]['topic'], {'n': 'different'}, now=2)
        with self.assertRaises(OutboxConflict): self.ack()
        self.assertEqual(self.outbox.get(self.event['event_id'])['state'], 'leased')
        self.assertEqual(len(rows(self.outbox)), 2)

    def test_parent_key_and_duplicate_keys_rejected(self):
        with self.assertRaises(OutboxConflict):
            self.ack(events=[{**self.events[0], 'idempotency_key': 'task:key'}])
        with self.assertRaises(ValueError): self.ack(events=[self.events[0], self.events[0]])
        self.assertEqual(len(rows(self.outbox)), 1)

    def test_concurrent_cancel_cannot_observe_half_committed_completion(self):
        inserted = threading.Event(); release = threading.Event(); cancel_started = threading.Event()
        acknowledgements, cancellations, errors = [], [], []
        original = self.outbox.enqueue_in_transaction
        def paused(db, key, *args, **kwargs):
            value = original(db, key, *args, **kwargs)
            if key == 'completion:one':
                inserted.set()
                if not release.wait(5): raise RuntimeError('fixture synchronization timeout')
            return value
        def complete():
            try: acknowledgements.append(self.ack())
            except Exception as exc: errors.append(exc)
        def cancel():
            cancel_started.set()
            try: cancellations.append(self.outbox.cancel(self.event['event_id'], 'operator', now=3))
            except ValueError as exc: cancellations.append(str(exc))
        with patch.object(self.outbox, 'enqueue_in_transaction', paused):
            a = threading.Thread(target=complete); a.start()
            try:
                self.assertTrue(inserted.wait(3))
                # A separate reader sees the original leased task and no announcements.
                self.assertEqual(len(rows(self.outbox)), 1)
                self.assertEqual(self.outbox.get(self.event['event_id'])['state'], 'leased')
                c = threading.Thread(target=cancel); c.start()
                self.assertTrue(cancel_started.wait(2))
            finally:
                release.set(); a.join(5)
                if 'c' in locals(): c.join(5)
        self.assertFalse(a.is_alive()); self.assertFalse(c.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(acknowledgements[0]['state'], 'acknowledged')
        self.assertIn('acknowledged', cancellations[0])
        self.assertEqual(len(rows(self.outbox)), 3)

    def test_nonfinite_clock_and_invalid_envelope_rejected(self):
        for value in [True, float('nan'), float('inf'), '3']:
            with self.subTest(clock=value), self.assertRaises(ValueError): self.ack(now=value)
        for value in [[], {}, [self.events[0]] * 17, [{'topic': 'x'}]]:
            with self.subTest(events=value), self.assertRaises(ValueError): self.ack(events=value)
        self.assertEqual(len(rows(self.outbox)), 1)


if __name__ == '__main__':
    unittest.main()
