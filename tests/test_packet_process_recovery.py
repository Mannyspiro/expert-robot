"""Canonical Hermes checker-only recovery; process and authority are fixtures.

The live OCI drill separately measures actual systemd execution. These tests do
not establish provider authentication, model review or independent verification.
"""
import base64
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

import test_branch_worker as worker_fixture
from merlin.branch_research import canonical, digest
from merlin.branch_registry import RegistryBranchSession
from merlin.branch_task_recovery import task_path
from merlin.hermes_process import ProcessLimits
from merlin.hermes_systemd import SystemdFixedPythonProcess, _CHILD, _properties
from merlin.packet_process import FixedPacketExecutor, packet_executor_identity


class PacketRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.reset_fixture()

    def reset_fixture(self):
        self.f = worker_fixture.BranchWorkerTests()
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        f = self.f
        program = f.root / 'fixed.py'; program.write_text('print("ok")\n')
        self.process = SystemdFixedPythonProcess(program, hashlib.sha256(program.read_bytes()).hexdigest())
        self.limits = ProcessLimits(cpu_seconds=1, wall_seconds=2, output_bytes=8192)
        self.process_allowed = True; self.recovery_allowed = True
        self.launches = 0; self.checker_calls = 0; self.interrupt_checker = False
        self.checker_result = {'passed': True, 'detail': 'Synthetic exact completed process check'}
        self.after_check = lambda: None
        self.mutate_receipt = lambda result: result
        identity = packet_executor_identity(program_sha256=self.process.sha256, checker_sha256='b' * 64,
            input_ref=f.evidence_ref, limits=self.limits, tasks_max=self.process.tasks_max)
        f.params['executor_sha256'] = identity
        f.session = RegistryBranchSession(f.registry, **f.params)
        self.adapter = FixedPacketExecutor(f.session, self.process, input_ref=f.evidence_ref,
            limits=self.limits, checker=self.checker, checker_sha256='b' * 64,
            authorize=lambda _: self.process_allowed,
            recovery_authorizer=lambda *_: self.recovery_allowed)
        f.handlers = f.make_handlers(self.adapter)
        f.worker = f.make_worker(max_attempts=20)

    def task(self, **changes):
        return self.f.task(artifact_refs=[deepcopy(self.f.frame_ref), deepcopy(self.f.evidence_ref)], **changes)

    def checker(self, raw, result):
        self.checker_calls += 1
        if self.interrupt_checker:
            raise OSError('synthetic checker interruption after persisted process')
        self.after_check()
        return deepcopy(self.checker_result)

    def process_result(self, raw, **kwargs):
        self.launches += 1
        if kwargs['authorize']({'phase': 'synthetic_process'}) is not True:
            raise PermissionError('synthetic process authority denied')
        unit = 'merlin-fixed-' + '1' * 32 + '.service'
        setup = {'unit': unit, 'pid': 1234, 'uid': 1001, 'cgroup': '/system.slice/' + unit,
            'controllers': {'memory.max': str(self.limits.memory_bytes), 'memory.swap.max': '0',
                'pids.max': str(self.process.tasks_max), 'cpu.max': '100000 100000'},
            'program_sha256': self.process.sha256}
        out = b'MERLIN_CGROUP_READY=' + json.dumps(setup, sort_keys=True).encode() + b'\nok\n'
        state = {'LoadState': 'not-found', 'ActiveState': 'inactive', 'SubState': 'dead',
            'ControlGroup': '', 'Result': 'success', 'ExecMainCode': '0', 'ExecMainStatus': '0'}
        result = {'schema': 'merlin-systemd-process-result/1', 'status': 'completed', 'returncode': 0,
            'program_sha256': self.process.sha256, 'bootstrap_sha256': hashlib.sha256(_CHILD.encode()).hexdigest(),
            'input_sha256': hashlib.sha256(raw).hexdigest(), 'elapsed_seconds': 0.01,
            'limits': {'program_sha256': self.process.sha256, 'unit': unit,
                'limits': _properties(self.limits, self.process.tasks_max), 'tasks_max': self.process.tasks_max,
                'isolation': 'systemd_cgroup_v2', 'compute_budget_units_enforced': False},
            'kernel_setup': setup, 'manager_result': deepcopy(state), 'cleanup': deepcopy(state),
            'io_transport': 'manager_opened_files', 'manager_stderr': '', 'stdout': 'ok\n', 'stderr': '',
            'stdout_base64': base64.b64encode(out).decode(), 'stderr_base64': '',
            'stdout_sha256': hashlib.sha256(out).hexdigest(), 'stderr_sha256': hashlib.sha256(b'').hexdigest(),
            'qualification': False, 'promotion_authority': False}
        return self.mutate_receipt(result)

    def step(self):
        with patch.object(self.process, 'run', side_effect=self.process_result):
            return self.f.worker.run_once()

    def interrupt(self):
        self.interrupt_checker = True
        self.event = self.f.enqueue(self.task())
        result = self.step()
        self.interrupt_checker = False
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(self.launches, 1)
        self.assertEqual(self.f.session.status()['reconciliation_required'], 'a')
        self.assertIsNotNone(self.f.session._read('processes/a.json'))

    def decision(self, name='decision', **changes):
        f = self.f
        body = {'schema': 'merlin-packet-recovery-decision/1',
            'request_ref': f.registry.artifact_ref('test', task_path('tick-1') + 'request.json'),
            'intent_ref': f.registry.artifact_ref('test', f.session.base + 'intents/a.json'),
            'process_ref': f.registry.artifact_ref('test', f.session.base + 'processes/a.json'),
            'expected_state_sha256': digest(f.session.status()), 'source_commit': f.params['source_commit'],
            'session_id': f.session.session_id, 'executor_sha256': self.adapter.identity,
            'input_ref': deepcopy(f.evidence_ref), 'checker_sha256': 'b' * 64,
            'action': 'check_completed_process_only', 'checker_replay_authorized': True,
            'process_reexecution_authorized': False, 'reviewer_id': 'synthetic-host-reviewer',
            'reason': 'Explicitly authorize one checker replay from exact completed process bytes',
            'authority': 'reconcile_only', 'qualification': False, 'promotion_authority': False}
        body.update(changes)
        path = 'recovery-decisions/' + name + '.json'
        f.registry.put_artifact('test', path, canonical(body).encode(), 'application/json')
        return f.registry.artifact_ref('test', path)

    def recover(self, ref, **worker_changes):
        handler = lambda task, context: self.adapter.reconcile(task, context, decision_ref=ref)
        worker = self.f.make_worker(handlers=self.f.make_handlers(handler), max_attempts=20, **worker_changes)
        with patch.object(self.process, 'run', side_effect=AssertionError('recovery must never launch a process')):
            return worker.run_once()

    def assert_unresolved(self):
        self.assertEqual(self.launches, 1)
        self.assertIsNone(self.f.session._read('outcomes/a.json'))
        self.assertEqual(self.f.session.status()['reconciliation_required'], 'a')

    def test_recover_completed_process_without_relaunch_and_replay_exact(self):
        self.interrupt()
        failure_ref = self.f.session._read('failures/a.json')[1]
        self.assertNotEqual(self.step()['status'], 'completed')
        first = self.recover(self.decision())
        self.assertEqual(first['status'], 'completed'); self.assertEqual(self.launches, 1)
        self.assertEqual(self.checker_calls, 2)
        self.assertEqual(self.f.session._read('failures/a.json')[1], failure_ref)
        recovery_ref = first['receipt']['result']['metadata']['task_recovery_ref']
        recovery = json.loads(self.f.registry.read_artifact_ref(recovery_ref)['content'])
        self.assertFalse(recovery['process_reexecuted']); self.assertFalse(recovery['evaluator_reexecuted'])
        self.assertEqual(recovery['outcome_ref'], self.f.session._read('outcomes/a.json')[1])
        self.assertEqual(recovery['process_ref'], self.f.session._read('processes/a.json')[1])
        self.assertTrue(self.f.registry.resolve_artifact_ref(recovery['checker_result_ref'])['verified'])
        self.f.enqueue(self.task(), key='fresh-worker-replay')
        replay = self.step()
        self.assertEqual(first['receipt'], replay['receipt']); self.assertEqual(self.launches, 1)
        self.assertEqual(first['receipt']['result']['cace_verification']['verification_status'], 'blocked_missing_credentials')

    def test_same_recovery_decision_replays_after_successor(self):
        self.interrupt(); ref = self.decision(); first = self.recover(ref)
        self.assertEqual(first['status'], 'completed')
        self.f.enqueue(self.task(task_id='tick-2'), key='next'); self.assertEqual(self.step()['status'], 'completed')
        self.f.enqueue(self.task(), key='repeat-recovery'); replay = self.recover(ref)
        self.assertEqual(first['receipt'], replay['receipt']); self.assertEqual(self.launches, 2)
        self.assertEqual(self.checker_calls, 3)

    def test_failed_check_is_recorded_and_dependency_stays_waiting(self):
        self.interrupt(); self.checker_result = {'passed': False, 'detail': 'Measured output mismatch'}
        self.assertEqual(self.recover(self.decision())['status'], 'completed')
        self.assertEqual(self.f.session.status()['branches'],
            [{'id': 'a', 'status': 'failed_local_check'}, {'id': 'b', 'status': 'waiting'}])
        self.f.enqueue(self.task(task_id='tick-2'), key='next'); self.assertEqual(self.step()['status'], 'completed')
        self.assertEqual(self.launches, 1)

    def test_checker_failure_remains_ambiguous_and_is_not_repeated(self):
        self.interrupt(); ref = self.decision(); self.interrupt_checker = True
        self.assertNotEqual(self.recover(ref)['status'], 'completed'); self.interrupt_checker = False
        self.assertNotEqual(self.recover(ref)['status'], 'completed')
        self.assertEqual(self.checker_calls, 2); self.assert_unresolved()
        failure = self.f.session._read_path(task_path('tick-1') + 'packet-check-failure.json')[0]
        self.assertEqual(failure['error_class'], 'OSError')

    def test_truthy_checker_result_cannot_publish_or_repeat(self):
        self.interrupt(); ref = self.decision(); self.checker_result = {'passed': 1, 'detail': 'Invalid Boolean'}
        self.assertNotEqual(self.recover(ref)['status'], 'completed')
        self.assertNotEqual(self.recover(ref)['status'], 'completed')
        self.assertEqual(self.checker_calls, 2); self.assert_unresolved()

    def test_missing_recovery_authorizer_is_rejected(self):
        self.interrupt(); self.adapter.recovery_authorizer = None
        self.assertEqual(self.recover(self.decision())['status'], 'rejected'); self.assert_unresolved()

    def test_truthy_recovery_authority_is_rejected(self):
        self.interrupt(); self.recovery_allowed = 1
        self.assertEqual(self.recover(self.decision())['status'], 'rejected'); self.assert_unresolved()

    def test_revoked_process_authority_is_rejected(self):
        self.interrupt(); self.process_allowed = False
        self.assertEqual(self.recover(self.decision())['status'], 'rejected'); self.assert_unresolved()

    def test_revoked_session_authority_is_rejected(self):
        self.interrupt(); self.f.allowed = False
        self.assertEqual(self.recover(self.decision())['status'], 'rejected'); self.assert_unresolved()

    def test_revocation_after_checker_prevents_publication_and_checker_retry(self):
        self.interrupt(); ref = self.decision()
        self.after_check = lambda: setattr(self, 'recovery_allowed', False)
        self.assertEqual(self.recover(ref)['status'], 'rejected'); self.assert_unresolved()
        self.recovery_allowed = True; self.after_check = lambda: None
        self.f.enqueue(self.task(), key='revocation-retry')
        self.assertNotEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.checker_calls, 2)

    def test_cancellation_after_checker_prevents_outcome_publication(self):
        self.interrupt(); ref = self.decision()
        self.after_check = lambda: self.f.outbox.cancel(self.event['event_id'], 'synthetic-operator')
        self.assertEqual(self.recover(ref)['status'], 'cancelled'); self.assert_unresolved()

    def test_stale_worker_lease_after_checker_prevents_outcome_publication(self):
        self.interrupt(); ref = self.decision()
        def transfer():
            row = self.f.outbox.get(self.event['event_id'])
            self.f.outbox.claim_next('successor', lease_seconds=120, now=row['lease_expires_at'] + 1)
        self.after_check = transfer
        self.assertEqual(self.recover(ref)['status'], 'lease_lost'); self.assert_unresolved()

    def test_changed_bindings_cannot_recover(self):
        changes = [dict(source_commit='f' * 40), dict(session_id='other'), dict(executor_sha256='f' * 64),
            dict(input_ref=self.f.frame_ref), dict(checker_sha256='c' * 64), dict(request_ref=self.f.frame_ref),
            dict(expected_state_sha256='0' * 64), dict(checker_replay_authorized=1),
            dict(process_reexecution_authorized=True), dict(promotion_authority=True)]
        for changed in changes:
            with self.subTest(changed=next(iter(changed))):
                self.reset_fixture(); self.interrupt()
                self.assertNotEqual(self.recover(self.decision(**changed))['status'], 'completed')
                self.assertEqual(self.checker_calls, 1); self.assert_unresolved()

    def test_wrong_process_or_intent_reference_is_rejected(self):
        for key in ('process_ref', 'intent_ref'):
            with self.subTest(key=key):
                self.reset_fixture(); self.interrupt()
                self.assertNotEqual(self.recover(self.decision(**{key: self.f.frame_ref}))['status'], 'completed')
                self.assertEqual(self.checker_calls, 1); self.assert_unresolved()

    def test_missing_process_cannot_be_invented_from_decision(self):
        self.interrupt(); ref = self.decision(); process_ref = self.f.session._read('processes/a.json')[1]
        (self.f.registry.blobs / process_ref['sha256'][:2] / process_ref['sha256'][2:]).unlink()
        self.assertNotEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.checker_calls, 1)

    def test_process_payload_tampering_is_rejected(self):
        self.interrupt(); ref = self.decision(); process_ref = self.f.session._read('processes/a.json')[1]
        (self.f.registry.blobs / process_ref['sha256'][:2] / process_ref['sha256'][2:]).write_bytes(b'{}')
        self.assertNotEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.checker_calls, 1)

    def test_noncompleted_or_unclean_process_evidence_stays_blocked(self):
        mutations = [lambda r: {**r, 'returncode': 1}, lambda r: {**r, 'stdout': 'forged'},
            lambda r: {**r, 'cleanup': {**r['cleanup'], 'ActiveState': 'active'}},
            lambda r: {**r, 'cleanup': {**r['cleanup'], 'ControlGroup': '/system.slice/remaining'}},
            lambda r: {**r, 'stdout_sha256': '0' * 64},
            lambda r: {**r, 'bootstrap_sha256': '0' * 64},
            lambda r: {**r, 'limits': {**r['limits'], 'tasks_max': 32}}]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                self.reset_fixture(); self.mutate_receipt = mutate; self.interrupt()
                self.assertNotEqual(self.recover(self.decision())['status'], 'completed')
                self.assertEqual(self.checker_calls, 1); self.assert_unresolved()

    def test_noncompleted_process_is_not_recovered_even_with_complete_bytes(self):
        self.mutate_receipt = lambda r: {**r, 'status': 'failed', 'returncode': 1}
        self.event = self.f.enqueue(self.task()); original = self.f.session._put_path
        def interrupt_outcome(path, body):
            if path.endswith('/outcomes/a.json'): raise OSError('synthetic publication stop')
            return original(path, body)
        with patch.object(self.f.session, '_put_path', side_effect=interrupt_outcome):
            self.assertEqual(self.step()['status'], 'pending')
        self.assertNotEqual(self.recover(self.decision())['status'], 'completed')
        self.assertEqual(self.checker_calls, 0); self.assert_unresolved()

    def test_different_decision_cannot_replace_reserved_recovery(self):
        self.interrupt(); first = self.decision(); original = self.f.session._put_path
        def stop(path, body):
            value = original(path, body)
            if path.endswith('/packet-recovery.json'): raise OSError('after reservation')
            return value
        with patch.object(self.f.session, '_put_path', side_effect=stop): self.recover(first)
        self.assertNotEqual(self.recover(self.decision(name='different', reason='different approval'))['status'], 'completed')
        self.assertEqual(self.checker_calls, 1)
        self.assertEqual(self.recover(first)['status'], 'completed'); self.assertEqual(self.launches, 1)

    def test_recovery_resumes_from_durable_publication_boundaries(self):
        suffixes = ['/packet-recovery.json', '/packet-check-result.json', '/outcomes/a.json',
                    '/recovery.json', '/result.json']
        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                self.reset_fixture(); self.interrupt(); ref = self.decision(); original = self.f.session._put_path
                fired = []
                def crash(path, body):
                    value = original(path, body)
                    if path.endswith(suffix) and not fired:
                        fired.append(path); raise OSError('synthetic stop after durable publication')
                    return value
                with patch.object(self.f.session, '_put_path', side_effect=crash):
                    self.assertEqual(self.recover(ref)['status'], 'pending')
                self.assertEqual(self.recover(ref)['status'], 'completed')
                self.assertEqual(self.launches, 1); self.assertEqual(self.checker_calls, 2)
                for name in ('packet-recovery.json', 'packet-check-intent.json', 'packet-check-result.json', 'recovery.json', 'result.json'):
                    self.assertEqual(len(self.f.registry.artifact_history('test', task_path('tick-1') + name)), 1)

    def test_interruption_after_checker_intent_never_implies_permission_to_repeat(self):
        self.interrupt(); ref = self.decision(); original = self.f.session._put_path
        def stop(path, body):
            value = original(path, body)
            if path.endswith('/packet-check-intent.json'): raise OSError('checker invocation uncertainty')
            return value
        with patch.object(self.f.session, '_put_path', side_effect=stop): self.recover(ref)
        self.assertNotEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.checker_calls, 1)
        self.assert_unresolved()

    def test_revocation_before_task_publication_withholds_result(self):
        self.interrupt(); ref = self.decision(); original = self.f.session._snapshot_locked
        def revoke(**kwargs):
            value = original(**kwargs); self.recovery_allowed = False; return value
        with patch.object(self.f.session, '_snapshot_locked', side_effect=revoke):
            self.assertEqual(self.recover(ref)['status'], 'rejected')
        self.assertIsNone(self.f.session._read_path(task_path('tick-1') + 'result.json'))
        self.recovery_allowed = True; self.f.enqueue(self.task(), key='approved-publication-retry')
        self.assertEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.checker_calls, 2)

    def test_recovery_authorizer_cannot_mutate_bound_decision(self):
        self.interrupt(); ref = self.decision()
        def mutate(reference, decision): reference.clear(); decision.clear(); return True
        self.adapter.recovery_authorizer = mutate
        self.assertEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.launches, 1)

    def test_mutating_checker_cannot_rewrite_recorded_process(self):
        self.interrupt(); ref = self.decision(); prior = self.f.session._read('processes/a.json')
        def mutate(raw, result): result.clear(); return {'passed': True, 'detail': 'Detached checker fixture'}
        self.adapter.checker = mutate
        self.assertEqual(self.recover(ref)['status'], 'completed')
        self.assertEqual(self.f.session._read('processes/a.json'), prior)

    def test_tasks_max_is_part_of_plan_identity(self):
        first = packet_executor_identity(program_sha256=self.process.sha256, checker_sha256='b' * 64,
            input_ref=self.f.evidence_ref, limits=self.limits, tasks_max=8)
        second = packet_executor_identity(program_sha256=self.process.sha256, checker_sha256='b' * 64,
            input_ref=self.f.evidence_ref, limits=self.limits, tasks_max=32)
        self.assertNotEqual(first, second)
        for invalid in (True, 0, 33, 8.0):
            with self.assertRaises(ValueError):
                packet_executor_identity(program_sha256=self.process.sha256, checker_sha256='b' * 64,
                    input_ref=self.f.evidence_ref, limits=self.limits, tasks_max=invalid)

    def test_changed_process_task_ceiling_cannot_launch(self):
        self.process.tasks_max = 32; self.f.enqueue(self.task())
        self.assertNotEqual(self.step()['status'], 'completed'); self.assertEqual(self.launches, 0)

    def test_changed_process_task_ceiling_cannot_recover(self):
        self.interrupt(); ref = self.decision(); self.process.tasks_max = 32
        self.assertNotEqual(self.recover(ref)['status'], 'completed'); self.assertEqual(self.checker_calls, 1)
        self.assert_unresolved()

    def test_session_revocation_inside_process_authorizer_blocks_checker(self):
        def revoke(policy):
            if policy['process_policy'].get('phase') == 'check_result':
                self.f.allowed = False
            return True
        self.adapter.authorize = revoke; self.f.enqueue(self.task())
        self.assertEqual(self.step()['status'], 'rejected')
        self.assertEqual(self.checker_calls, 0)
        self.assertIsNone(self.f.session._read('processes/a.json'))
        self.assert_unresolved()

    def test_revocation_after_process_receipt_blocks_checker(self):
        original = self.f.session._put_path
        def revoke(path, body):
            ref = original(path, body)
            if path.endswith('/processes/a.json'):
                self.process_allowed = False
            return ref
        self.f.enqueue(self.task())
        with patch.object(self.f.session, '_put_path', side_effect=revoke):
            self.assertEqual(self.step()['status'], 'rejected')
        self.assertIsNotNone(self.f.session._read('processes/a.json'))
        self.assertEqual(self.checker_calls, 0); self.assert_unresolved()

    def test_process_revocation_inside_normal_checker_withholds_outcome(self):
        self.after_check = lambda: setattr(self, 'process_allowed', False)
        self.f.enqueue(self.task())
        self.assertEqual(self.step()['status'], 'rejected')
        self.assertEqual(self.checker_calls, 1); self.assert_unresolved()


if __name__ == '__main__':
    unittest.main()
