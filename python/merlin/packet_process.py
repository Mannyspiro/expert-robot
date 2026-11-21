"""Host-owned fixed packet execution through existing recoverable Hermes tasks.

No model, provider, privilege grant or endpoint is created. The existing systemd
supervisor enforces resource ceilings; the canonical branch task owns replay and
ambiguous-intent fencing. Host checker results remain local checks, not proof.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict
import base64
import hashlib
import json
import math
import re
from .artifact_ref import ArtifactRef
from .branch_research import canonical, digest
from .branch_registry import BranchSessionConflict, MAX_RECORD, RegistryBranchSession
from .branch_task_recovery import RecoverableBranchExecutor, _snapshot_state, guard_unfinished_tasks, task_path
from .hermes_process import ProcessLimits
from .hermes_systemd import SystemdFixedPythonProcess, _CHILD, _properties


def packet_executor_identity(*, program_sha256, checker_sha256, input_ref, limits, tasks_max=8):
    for value in (program_sha256, checker_sha256):
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('exact program and checker identities required')
    if not isinstance(limits, ProcessLimits):
        raise ValueError('typed host-owned limits required')
    limits.validate()
    if type(tasks_max) is not int or not 1 <= tasks_max <= 32:
        raise ValueError('bounded integer fixed process task ceiling required')
    if limits.output_bytes > 16384:
        raise ValueError('bounded canonical receipt requires at most 16 KiB of process output')
    return digest({'schema': 'merlin-packet-process-identity/2', 'program_sha256': program_sha256,
        'checker_sha256': checker_sha256, 'input_ref': ArtifactRef.from_mapping(input_ref).to_dict(),
        'limits': asdict(limits), 'tasks_max': tasks_max})


class FixedPacketExecutor:
    def __init__(self, session, process, *, input_ref, limits, checker, checker_sha256, authorize,
                 recovery_authorizer=None):
        if (not isinstance(session, RegistryBranchSession) or not isinstance(process, SystemdFixedPythonProcess)
                or not callable(checker) or not callable(authorize)
                or (recovery_authorizer is not None and not callable(recovery_authorizer))):
            raise ValueError('canonical session and actual host process/checker/authority required')
        self.ref = session._ref(input_ref)
        self.identity = packet_executor_identity(program_sha256=process.sha256,
            checker_sha256=checker_sha256, input_ref=self.ref, limits=limits, tasks_max=process.tasks_max)
        if session.spec['executor']['sha256'] != self.identity:
            raise ValueError('session executor binding differs from fixed packet plan')
        self.session, self.process, self.limits = session, process, limits
        self.checker, self.checker_sha256, self.authorize = checker, checker_sha256, authorize
        self.recovery_authorizer = recovery_authorizer

    def _plan(self, context):
        if not any(canonical(ref) == canonical(self.ref) for ref in context.artifact_refs):
            raise PermissionError('exact process input absent from admitted Hermes task')
        if packet_executor_identity(program_sha256=self.process.sha256, checker_sha256=self.checker_sha256,
                input_ref=self.ref, limits=self.limits, tasks_max=self.process.tasks_max) != self.identity:
            raise RuntimeError('fixed process plan changed')
        if self.session.spec['executor']['sha256'] != self.identity:
            raise RuntimeError('session fixed process identity changed')

    def _gate(self, context, policy):
        self._plan(context)
        context.check_cancelled()
        self.session._authorize()
        if self.authorize({'task_id': context.task_id, 'executor_sha256': self.identity,
                'input_ref': deepcopy(self.ref), 'process_policy': deepcopy(policy)}) is not True:
            raise PermissionError('current process authority required')
        # Host callbacks receive detached values; recheck the live admitted plan.
        self._plan(context)
        context.check_cancelled()
        self.session._authorize()

    @staticmethod
    def _check(value):
        if (not isinstance(value, dict) or set(value) != {'passed', 'detail'}
                or type(value['passed']) is not bool or not isinstance(value['detail'], str)
                or not value['detail'].strip() or len(value['detail']) > 2000):
            raise ValueError('host checker must return a bounded measured Boolean outcome')
        return deepcopy(value)

    def __call__(self, task, context):
        self._plan(context)

        def gate(policy):
            self._gate(context, policy)
            return True

        def evaluate(branch, intent):
            if not gate({'phase': 'read_input'}):
                raise PermissionError('current process authority required')
            raw = self.session.registry.read_artifact_ref(self.ref, max_bytes=65536)['content']
            result = self.process.run(raw, limits=self.limits, context=context, authorize=gate)
            if (not isinstance(result, dict) or result.get('schema') != 'merlin-systemd-process-result/1'
                    or result.get('input_sha256') != hashlib.sha256(raw).hexdigest()
                    or result.get('program_sha256') != self.process.sha256
                    or result.get('qualification') is not False or result.get('promotion_authority') is not False):
                raise ValueError('exact non-authoritative process receipt required')
            setup = result.get('kernel_setup')
            if (not isinstance(setup, dict) or type(setup.get('uid')) is not int or setup['uid'] <= 0
                    or setup.get('program_sha256') != self.process.sha256):
                raise ValueError('actual non-root kernel setup evidence required')
            if not gate({'phase': 'check_result'}):
                raise PermissionError('process approval revoked before result acceptance')
            ref = self.session._put('processes/' + branch + '.json', {
                'schema': 'merlin-branch-packet-process/1', 'task_id': context.task_id,
                'intent_sha256': digest(intent), 'executor_sha256': self.identity,
                'input_ref': self.ref, 'checker_sha256': self.checker_sha256,
                'process': result, 'qualification': False, 'promotion_authority': False})
            gate({'phase': 'invoke_checker'})
            check = (self.checker(raw, deepcopy(result)) if result.get('status') == 'completed'
                     else {'passed': False, 'detail': 'Fixed process did not complete: ' + str(result.get('status'))})
            check = self._check(check)
            gate({'phase': 'accept_check'})
            return {**check, 'artifact_refs': [ref, deepcopy(self.ref)]}

        return RecoverableBranchExecutor(self.session, evaluate, budget=1)(task, context)

    def _completed_process(self, record, *, raw, task_id, intent):
        """Admit the full recorded fixed-process result, never a supplied verdict.

        This is structural and byte-integrity validation of host-produced evidence.
        The separately provisioned recovery authorizer remains the trust boundary.
        """
        keys = {'schema', 'task_id', 'intent_sha256', 'executor_sha256', 'input_ref',
                'checker_sha256', 'process', 'qualification', 'promotion_authority'}
        if (not isinstance(record, dict) or set(record) != keys
                or record['schema'] != 'merlin-branch-packet-process/1'
                or record['task_id'] != task_id or record['intent_sha256'] != digest(intent)
                or record['executor_sha256'] != self.identity
                or canonical(record['input_ref']) != canonical(self.ref)
                or record['checker_sha256'] != self.checker_sha256
                or record['qualification'] is not False or record['promotion_authority'] is not False):
            raise BranchSessionConflict('completed process does not bind the exact task and intent')
        result = record['process']
        if (not isinstance(result, dict) or result.get('schema') != 'merlin-systemd-process-result/1'
                or result.get('status') != 'completed' or type(result.get('returncode')) is not int
                or result['returncode'] != 0 or result.get('program_sha256') != self.process.sha256
                or result.get('input_sha256') != hashlib.sha256(raw).hexdigest()
                or result.get('bootstrap_sha256') != hashlib.sha256(_CHILD.encode()).hexdigest()
                or result.get('io_transport') != 'manager_opened_files'
                or result.get('qualification') is not False or result.get('promotion_authority') is not False):
            raise BranchSessionConflict('intact completed fixed-process evidence required')
        setup = result.get('kernel_setup')
        if (not isinstance(setup, dict)
                or set(setup) != {'unit', 'pid', 'uid', 'cgroup', 'controllers', 'program_sha256'}
                or type(setup['pid']) is not int or setup['pid'] <= 0
                or type(setup['uid']) is not int or setup['uid'] <= 0
                or setup['program_sha256'] != self.process.sha256
                or not isinstance(setup['unit'], str)
                or not re.fullmatch(r'merlin-fixed-[0-9a-f]{32}\.service', setup['unit'])
                or setup['cgroup'] != '/system.slice/' + setup['unit']):
            raise BranchSessionConflict('exact non-root fixed-process kernel identity required')
        expected_policy = {'program_sha256': self.process.sha256, 'unit': setup['unit'],
            'limits': _properties(self.limits, self.process.tasks_max), 'tasks_max': self.process.tasks_max,
            'isolation': 'systemd_cgroup_v2', 'compute_budget_units_enforced': False}
        if canonical(result.get('limits')) != canonical(expected_policy):
            raise BranchSessionConflict('recorded process limits differ from admitted plan')
        controls = setup['controllers']
        if (not isinstance(controls, dict)
                or set(controls) != {'memory.max', 'memory.swap.max', 'pids.max', 'cpu.max'}
                or controls['memory.max'] != str(self.limits.memory_bytes)
                or controls['memory.swap.max'] != '0' or controls['pids.max'] != str(self.process.tasks_max)
                or not isinstance(controls['cpu.max'], str)
                or not re.fullmatch(r'[1-9][0-9]{0,11} [1-9][0-9]{0,11}', controls['cpu.max'])):
            raise BranchSessionConflict('recorded aggregate kernel ceilings differ')
        quota, period = map(int, controls['cpu.max'].split())
        if quota != self.limits.cpu_cores * period:
            raise BranchSessionConflict('recorded CPU rate differs')
        cleanup, manager = result.get('cleanup'), result.get('manager_result')
        if (not isinstance(cleanup, dict) or cleanup.get('ControlGroup') != ''
                or cleanup.get('ActiveState') not in {'inactive', 'failed'}
                or cleanup.get('SubState') not in {'dead', 'failed'}
                or not isinstance(manager, dict) or manager.get('Result') != 'success'
                or manager.get('ExecMainStatus') != '0'):
            raise BranchSessionConflict('completed process cleanup is not confirmed')
        elapsed = result.get('elapsed_seconds')
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('finite process duration required')
        if not isinstance(result.get('manager_stderr'), str) or len(result['manager_stderr'].encode()) > 32768:
            raise ValueError('bounded manager diagnostics required')
        streams = {}
        for name in ('stdout', 'stderr'):
            encoded = result.get(name + '_base64')
            if not isinstance(encoded, str) or len(encoded) > (self.limits.output_bytes * 2):
                raise ValueError('bounded exact process stream required')
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError('invalid process stream encoding') from exc
            if (len(data) > self.limits.output_bytes // 2
                    or result.get(name + '_sha256') != hashlib.sha256(data).hexdigest()):
                raise BranchSessionConflict('process stream bytes or digest differ')
            streams[name] = data
        first, separator, payload = streams['stdout'].partition(b'\n')
        if (separator != b'\n' or not first.startswith(b'MERLIN_CGROUP_READY=')
                or canonical(json.loads(first[len(b'MERLIN_CGROUP_READY='):])) != canonical(setup)
                or result.get('stdout') != payload.decode('utf-8', errors='replace')
                or result.get('stderr') != streams['stderr'].decode('utf-8', errors='replace')):
            raise BranchSessionConflict('process payload does not match its recorded byte streams')
        return deepcopy(result)

    def reconcile(self, task, context, *, decision_ref):
        """Finish one explicitly authorized checker attempt from durable process bytes.

        No process or original evaluator runs here. Checker callbacks may have
        effects: an intent is persisted before the authorized checker replay. If
        that attempt has no durable result, even this method blocks a repeat.
        Recovery after a durable check/outcome is publication-only and idempotent.
        """
        if self.recovery_authorizer is None:
            raise PermissionError('separately provisioned fixed-process recovery authority required')
        self._plan(context)
        executor = RecoverableBranchExecutor(self.session, lambda *_: None, budget=1)
        identity = executor._identity(task, context)
        path = task_path(context.task_id)
        with self.session._locked():
            executor._gate(context)
            request, request_ref = executor._request(identity, path)
            decision_ref = self.session._ref(decision_ref)
            raw_decision = self.session.registry.read_artifact_ref(decision_ref, max_bytes=MAX_RECORD)['content']
            decision = json.loads(raw_decision)
            keys = {'schema', 'request_ref', 'intent_ref', 'process_ref', 'expected_state_sha256',
                'source_commit', 'session_id', 'executor_sha256', 'input_ref', 'checker_sha256',
                'action', 'checker_replay_authorized', 'process_reexecution_authorized',
                'reviewer_id', 'reason', 'authority', 'qualification', 'promotion_authority'}
            if (not isinstance(decision, dict) or set(decision) != keys
                    or canonical(decision).encode() != raw_decision
                    or decision['schema'] != 'merlin-packet-recovery-decision/1'
                    or canonical(decision['request_ref']) != canonical(request_ref)
                    or decision['source_commit'] != self.session.spec['source_commit']
                    or decision['session_id'] != self.session.session_id
                    or decision['executor_sha256'] != self.identity
                    or canonical(decision['input_ref']) != canonical(self.ref)
                    or decision['checker_sha256'] != self.checker_sha256
                    or decision['action'] != 'check_completed_process_only'
                    or decision['checker_replay_authorized'] is not True
                    or decision['process_reexecution_authorized'] is not False
                    or decision['authority'] != 'reconcile_only'
                    or decision['qualification'] is not False or decision['promotion_authority'] is not False
                    or not isinstance(decision['expected_state_sha256'], str)
                    or not re.fullmatch('[0-9a-f]{64}', decision['expected_state_sha256'])
                    or any(not isinstance(decision[k], str) or not decision[k].strip() or len(decision[k]) > 2000
                           for k in ('reviewer_id', 'reason'))):
                raise ValueError('exact checker-only fixed-process recovery decision required')

            def gate(phase):
                self._gate(context, {'phase': 'packet_recovery_' + phase,
                    'decision_ref': deepcopy(decision_ref), 'checker_replay_authorized': True,
                    'process_reexecution_authorized': False})
                self.session._frame()
                if self.recovery_authorizer(deepcopy(decision_ref), deepcopy(decision)) is not True:
                    raise PermissionError('exact checker replay decision not currently authorized by host')
                if canonical(executor._identity(task, context)) != canonical(identity):
                    raise BranchSessionConflict('admitted recovery task or context changed')
                self._plan(context)
                context.check_cancelled()
                self.session._authorize()

            gate('read_evidence')
            intent_ref = self.session._ref(decision['intent_ref'])
            process_ref = self.session._ref(decision['process_ref'])
            intent_raw = self.session.registry.read_artifact_ref(intent_ref, max_bytes=MAX_RECORD)['content']
            intent = json.loads(intent_raw)
            branch = intent.get('branch') if isinstance(intent, dict) else None
            if (branch not in self.session.branches or canonical(intent).encode() != intent_raw
                    or canonical(self.session._read('intents/' + branch + '.json')) != canonical((intent, intent_ref))
                    or process_ref['logical_path'] != self.session.base + 'processes/' + branch + '.json'
                    or process_ref['version'] != 1):
                raise BranchSessionConflict('exact pending branch and process paths required')
            recorded = self.session._read('processes/' + branch + '.json')
            if recorded is None or canonical(recorded[1]) != canonical(process_ref):
                raise BranchSessionConflict('exact completed process receipt unavailable')
            raw_input = self.session.registry.read_artifact_ref(self.ref, max_bytes=65536)['content']
            process_result = self._completed_process(recorded[0], raw=raw_input, task_id=context.task_id, intent=intent)
            plan_ref, done, pending = self.session._state()
            before = request['starting_state']['completed']
            prefix = dict(list(done.items())[:before])
            expected_start = self.session._view(plan_ref, prefix, None)
            expected_pending = self.session._view(plan_ref, prefix, branch)
            if (canonical(expected_start) != canonical(request['starting_state'])
                    or canonical(intent) != canonical(self.session._intent(self.session.branches[branch], prefix, plan_ref))
                    or digest(expected_pending) != decision['expected_state_sha256']):
                raise BranchSessionConflict('recovery intent or reviewed starting state differs')
            original_failure = self.session._read('failures/' + branch + '.json')
            original_failure_ref = original_failure[1] if original_failure else None
            reservation_body = {'schema': 'merlin-packet-recovery-reservation/1',
                'decision_ref': decision_ref, 'request_ref': request_ref, 'intent_ref': intent_ref,
                'process_ref': process_ref, 'expected_state': expected_pending,
                'input_ref': self.ref, 'executor_sha256': self.identity, 'checker_sha256': self.checker_sha256,
                'original_failure_ref': original_failure_ref,
                'qualification': False, 'promotion_authority': False}
            reservation = self.session._read_path(path + 'packet-recovery.json')
            if reservation is None:
                if (pending != branch or len(done) != before
                        or self.session._read_path(path + 'result.json') is not None):
                    raise BranchSessionConflict('new recovery requires the exact unresolved task state')
                guard_unfinished_tasks(self.session, request_ref)
                gate('reserve')
                recovery_ref = self.session._put_path(path + 'packet-recovery.json', reservation_body)
            else:
                if canonical(reservation[0]) != canonical(reservation_body):
                    raise BranchSessionConflict('a different fixed-process recovery decision is already bound')
                recovery_ref = reservation[1]

            check_intent_body = {'schema': 'merlin-packet-check-intent/1', 'recovery_ref': recovery_ref,
                'decision_ref': decision_ref, 'process_ref': process_ref, 'input_ref': self.ref,
                'checker_sha256': self.checker_sha256, 'checker_replay_authorized': True,
                'process_reexecution_authorized': False, 'qualification': False, 'promotion_authority': False}
            check_intent = self.session._read_path(path + 'packet-check-intent.json')
            check_record = self.session._read_path(path + 'packet-check-result.json')
            if check_intent is None:
                if check_record is not None or branch in done:
                    raise BranchSessionConflict('orphan checker result or recovered branch outcome')
                gate('checker_intent')
                check_intent_ref = self.session._put_path(path + 'packet-check-intent.json', check_intent_body)
                try:
                    gate('invoke_checker')
                    check = self._check(self.checker(raw_input, deepcopy(process_result)))
                    gate('store_check')
                    body = {'schema': 'merlin-packet-check-result/1', 'checker_intent_ref': check_intent_ref,
                        'recovery_ref': recovery_ref, 'process_ref': process_ref,
                        'checker_sha256': self.checker_sha256, 'check': check,
                        'qualification': False, 'promotion_authority': False}
                    check_ref = self.session._put_path(path + 'packet-check-result.json', body)
                    check_record = body, check_ref
                except Exception as exc:
                    # Retain the attempted checker boundary; no automatic callback retry.
                    self.session._put_path(path + 'packet-check-failure.json', {
                        'schema': 'merlin-packet-check-failure/1', 'checker_intent_ref': check_intent_ref,
                        'error_class': type(exc).__name__, 'reconciliation_required': True,
                        'qualification': False, 'promotion_authority': False})
                    raise
            else:
                if canonical(check_intent[0]) != canonical(check_intent_body):
                    raise BranchSessionConflict('checker attempt binding differs')
                check_intent_ref = check_intent[1]
                if check_record is None:
                    raise BranchSessionConflict('checker attempt has no durable result; explicit further reconciliation required')
            check = self._check(check_record[0].get('check'))
            expected_check = {'schema': 'merlin-packet-check-result/1', 'checker_intent_ref': check_intent_ref,
                'recovery_ref': recovery_ref, 'process_ref': process_ref, 'checker_sha256': self.checker_sha256,
                'check': check, 'qualification': False, 'promotion_authority': False}
            if canonical(check_record[0]) != canonical(expected_check):
                raise BranchSessionConflict('durable checker result binding differs')
            evidence_refs = [process_ref, self.ref, decision_ref, recovery_ref, check_intent_ref, check_record[1]]
            if original_failure_ref is not None:
                evidence_refs.append(original_failure_ref)
            evidence = self.session._evidence({**check, 'artifact_refs': evidence_refs})
            outcome = {'schema': 'merlin-registry-branch-outcome/1', 'intent_ref': intent_ref,
                'evidence': evidence, 'status': 'passed_local_check' if check['passed'] else 'failed_local_check',
                'qualification': False, 'promotion_authority': False}
            prior_outcome = self.session._read('outcomes/' + branch + '.json')
            if prior_outcome is not None and canonical(prior_outcome[0]) != canonical(outcome):
                raise BranchSessionConflict('branch outcome differs from the authorized recovery check')

            def task_recovery_body(state, outcome_ref):
                return {'schema': 'merlin-branch-task-recovery/1', 'request_ref': request_ref,
                    'decision_ref': decision_ref, 'state_sha256': digest(state),
                    'action': 'check_completed_process_only', 'evaluator_reexecuted': False,
                    'process_reexecuted': False, 'packet_recovery_ref': recovery_ref,
                    'checker_result_ref': check_record[1], 'process_ref': process_ref,
                    'intent_ref': intent_ref, 'outcome_ref': outcome_ref,
                    'original_failure_ref': original_failure_ref,
                    'qualification': False, 'promotion_authority': False}

            prior_result = self.session._read_path(path + 'result.json')
            if prior_result is not None:
                if prior_outcome is None:
                    raise BranchSessionConflict('task result has no recovered branch outcome')
                gate('replay')
                recovery = self.session._read_path(path + 'recovery.json')
                old_state = _snapshot_state(self.session, prior_result[0]['snapshot_ref'])
                if (recovery is None
                        or canonical(recovery[0]) != canonical(task_recovery_body(old_state, prior_outcome[1]))):
                    raise BranchSessionConflict('task recovery receipt differs')
                answer = executor._replay(request, request_ref, prior_result[0])
                gate('return_replay')
                return answer
            guard_unfinished_tasks(self.session, request_ref)
            gate('publish_outcome')
            outcome_ref = self.session._put('outcomes/' + branch + '.json', outcome)
            state = self.session.status()
            if executor._transition(request, state) != 1:
                raise BranchSessionConflict('recovery must complete exactly its one admitted branch')
            gate('publish_recovery')
            task_recovery_ref = self.session._put_path(path + 'recovery.json', task_recovery_body(state, outcome_ref))
            gate('publish_snapshot')
            snapshot_ref = self.session._snapshot_locked(expected_state=state)
            gate('publish_task_result')
            result = {'schema': 'merlin-branch-task-result/2', 'request_ref': request_ref,
                'snapshot_ref': snapshot_ref, 'recovery_ref': task_recovery_ref}
            self.session._put_path(path + 'result.json', result)
            answer = executor._replay(request, request_ref, result)
            gate('return_result')
            return answer
