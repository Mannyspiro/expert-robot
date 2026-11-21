"""Canonical-registry branch receipts with conservative interruption handling.

Host-owned, cooperative single-writer execution only. No second evidence DB,
provider, remote endpoint, sandbox, trust root or promotion authority is added.
A committed intent without an outcome requires external reconciliation; it is
never automatically dispatched again. This is not exactly-once external IO.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict
import fcntl
import json
import os
import re
import stat
from typing import Any, Callable, Mapping

from .artifact_ref import ArtifactRef
from .branch_research import Branch, branch_catalogue, choose_branch, canonical, digest
from .project_registry import MerlinRegistry

MAX_RECORD = 128 * 1024


class BranchSessionConflict(RuntimeError):
    """Stored or concurrent session state cannot safely be reused."""


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or value in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value):
        raise ValueError(label + " must be a bounded identifier")
    return value


class RegistryBranchSession:
    def __init__(self, registry: MerlinRegistry, *, project_id: str, session_id: str,
                 branches: tuple[Branch, ...], source_commit: str,
                 research_plan_ref: Mapping[str, Any], principal: str,
                 executor_id: str, executor_sha256: str,
                 frame_validator: Callable, approval: Callable, lease: Callable):
        if not isinstance(registry, MerlinRegistry):
            raise ValueError("canonical registry required")
        self.registry = registry
        self.project_id = _identifier(project_id, "project_id")
        self.session_id = _identifier(session_id, "session_id")
        if not isinstance(branches, tuple) or not 1 <= len(branches) <= 32:
            raise ValueError("one to 32 immutable branch definitions required")
        for node in branches:
            if not isinstance(node, Branch):
                raise ValueError("typed branch required")
            _identifier(node.id, "branch id")
            if (not isinstance(node.title, str) or not node.title.strip() or len(node.title) > 500
                    or type(node.priority) is not int or abs(node.priority) > 1000000
                    or type(node.exploratory) is not bool or not isinstance(node.prerequisites, tuple)):
                raise ValueError("invalid branch fields")
            for key in node.prerequisites:
                _identifier(key, "prerequisite")
        self.branches = branch_catalogue(branches)
        if not isinstance(source_commit, str) or not re.fullmatch('[0-9a-f]{40}', source_commit):
            raise ValueError("exact source commit required")
        if not isinstance(executor_sha256, str) or not re.fullmatch('[0-9a-f]{64}', executor_sha256):
            raise ValueError("exact executor digest required")
        if not isinstance(principal, str) or not principal.strip() or len(principal) > 200:
            raise ValueError("host principal required")
        if not all(callable(x) for x in (frame_validator, approval, lease)):
            raise ValueError("host frame, approval and lease validators required")
        self.frame_validator, self.approval, self.lease = frame_validator, approval, lease
        self.frame_ref = self._ref(research_plan_ref)
        self.spec = {'schema': 'merlin-registry-branch-plan/1',
                     'session_id': session_id, 'project_id': project_id,
                     'source_commit': source_commit, 'research_plan_ref': self.frame_ref,
                     'principal_sha256': digest(principal),
                     'executor': {'id': _identifier(executor_id, 'executor'), 'sha256': executor_sha256},
                     'effect_policy': 'no_automatic_retry_after_intent',
                     'branches': [asdict(node) for node in branches],
                     'qualification': False, 'promotion_authority': False}
        # JSON normalizes the dataclass tuples before persistence/replay comparison.
        self.spec = json.loads(canonical(self.spec))
        self.base = 'branch-research/' + session_id + '/'
        self._frame()
        self.registry.artifact_history(project_id, self.base + 'plan.json')

    def _ref(self, value):
        ref = ArtifactRef.from_mapping(value).to_dict()
        if ref['project_id'] != self.project_id:
            raise ValueError('cross-project artifact reference rejected')
        return ref

    def _frame(self):
        raw = self.registry.read_artifact_ref(self.frame_ref, max_bytes=MAX_RECORD)['content']
        frame = json.loads(raw)
        validated = self.frame_validator(deepcopy(frame))
        if (not isinstance(validated, Mapping) or canonical(validated) != canonical(frame)
                or frame.get('schema') != 'merlin-research-plan/1'
                or frame.get('source_commit') != self.spec['source_commit']
                or frame.get('qualification') is not False or frame.get('promotion_authority') is not False):
            raise ValueError('validated source-bound research frame required')
        return frame

    @contextmanager
    def _locked(self):
        # Reuse the canonical host workflow lock. Not protection from other code
        # deliberately bypassing advisory locking or a trusted in-process callback.
        descriptor = os.open(self.registry.root / 'dot-dual-coder.lock',
                             os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise BranchSessionConflict('regular lock file required')
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BranchSessionConflict('host workflow already running') from exc
            yield
        finally:
            os.close(descriptor)

    def _read(self, suffix):
        return self._read_path(self.base + suffix)

    def _read_path(self, path):
        history = self.registry.artifact_history(self.project_id, path)
        if not history:
            return None
        if len(history) != 1:
            raise BranchSessionConflict('immutable session path has multiple versions')
        ref = self.registry.artifact_ref(self.project_id, path, version=1)
        raw = self.registry.read_artifact_ref(ref, max_bytes=MAX_RECORD)['content']
        body = json.loads(raw)
        if canonical(body).encode('utf-8') != raw:
            raise BranchSessionConflict('noncanonical session record')
        return body, ref

    def _put(self, suffix, body):
        return self._put_path(self.base + suffix, body)

    def _put_path(self, path, body):
        raw = canonical(body).encode('utf-8')
        if len(raw) > MAX_RECORD:
            raise ValueError('session record byte ceiling')
        old = self._read_path(path)
        if old:
            if canonical(old[0]) != canonical(body):
                raise BranchSessionConflict('immutable session record differs')
            return old[1]
        self.registry.put_artifact(self.project_id, path, raw, 'application/json')
        return self.registry.artifact_ref(self.project_id, path, version=1)

    def _authorize(self):
        if self.approval(deepcopy(self.spec)) is not True or self.lease(deepcopy(self.spec)) is not True:
            raise PermissionError('current host approval and lease required')

    def _evidence(self, body):
        if (not isinstance(body, dict) or set(body) != {'passed', 'detail', 'artifact_refs'}
                or type(body['passed']) is not bool or not isinstance(body['detail'], str)
                or not body['detail'].strip() or len(body['detail']) > 2000
                or not isinstance(body['artifact_refs'], list) or not 1 <= len(body['artifact_refs']) <= 16):
            raise ValueError('bounded local outcome and exact evidence references required')
        refs = [self._ref(ref) for ref in body['artifact_refs']]
        if len({canonical(ref) for ref in refs}) != len(refs):
            raise ValueError('duplicate evidence reference')
        total = 0
        for ref in refs:
            raw = self.registry.read_artifact_ref(ref, max_bytes=2 * 1024 * 1024)['content']
            total += len(raw)
            if total > 2 * 1024 * 1024:
                raise ValueError('total evidence byte ceiling')
        return {'passed': body['passed'], 'detail': body['detail'], 'artifact_refs': refs}

    def _intent(self, node, done, plan_ref):
        body = {'schema': 'merlin-registry-branch-intent/1', 'plan_ref': plan_ref,
                'branch': node.id, 'index': len(done) + 1,
                'previous_outcome_ref': next(reversed(done.values()))['ref'] if done else None,
                'prerequisite_refs': {key: done[key]['ref'] for key in node.prerequisites},
                'executor': self.spec['executor'], 'qualification': False, 'promotion_authority': False}
        return {**body, 'idempotency_key': 'branch:' + digest(body)}

    def _state(self):
        plan = self._read('plan.json')
        intents = {key: self._read('intents/' + key + '.json') for key in self.branches}
        outcomes = {key: self._read('outcomes/' + key + '.json') for key in self.branches}
        if plan is None:
            if any(intents.values()) or any(outcomes.values()):
                raise BranchSessionConflict('orphan branch records')
            return None, {}, None
        if canonical(plan[0]) != canonical(self.spec):
            raise BranchSessionConflict('session source, principal, executor or plan changed')
        done, visited, pending = {}, set(), None
        while True:
            node = choose_branch(self.branches, done)
            if node is None:
                break
            intent, outcome = intents[node.id], outcomes[node.id]
            if intent is None:
                break
            visited.add(node.id)
            if intent[0] != self._intent(node, done, plan[1]):
                raise BranchSessionConflict('intent lineage differs from scheduling policy')
            if outcome is None:
                pending = node.id
                break
            body, ref = outcome
            if (set(body) != {'schema', 'intent_ref', 'evidence', 'status', 'qualification', 'promotion_authority'}
                    or body['schema'] != 'merlin-registry-branch-outcome/1'
                    or body['intent_ref'] != intent[1] or body['qualification'] is not False
                    or body['promotion_authority'] is not False):
                raise BranchSessionConflict('outcome identity or authority differs')
            evidence = self._evidence(body['evidence'])
            status = 'passed_local_check' if evidence['passed'] else 'failed_local_check'
            if body['status'] != status:
                raise BranchSessionConflict('outcome status differs from recorded check')
            done[node.id] = {'ref': ref, 'intent_ref': intent[1], 'body': body,
                             'status': 'verified' if evidence['passed'] else 'failed'}
        if any((intents[key] or outcomes[key]) and key not in visited for key in self.branches):
            raise BranchSessionConflict('out-of-order or orphan session record')
        return plan[1], done, pending

    def _project(self, done):
        for row in done.values():
            targets = [row['intent_ref']] + row['body']['evidence']['artifact_refs']
            for ref in targets:
                self.registry.relate('artifact-ref:' + digest(row['ref']), 'depends_on',
                                     'artifact-ref:' + digest(ref),
                                     {'source_ref': row['ref'], 'target_ref': ref, 'promotion_authority': False})

    def _view(self, plan, done, pending):
        rows = []
        for key, node in self.branches.items():
            status = (done[key]['body']['status'] if key in done else 'reconciliation_required'
                      if key == pending else 'waiting' if any(done.get(p, {}).get('status') != 'verified'
                      for p in node.prerequisites) else 'ready')
            rows.append({'id': key, 'status': status})
        selected = choose_branch(self.branches, done) if pending is None else None
        return {'schema': 'merlin-registry-branch-status/1', 'plan_ref': plan,
                'session_id': self.session_id, 'branches': rows,
                'outcome_refs': [row['ref'] for row in done.values()],
                'completed': len(done), 'selected': selected.id if selected else None,
                'reconciliation_required': pending, 'semantic_verification': 'not_established',
                'qualification': False, 'promotion_authority': False}

    def status(self):
        self._frame()
        return self._view(*self._state())

    def step(self, evaluate: Callable, *, check_cancelled: Callable, budget: int = 1):
        if type(budget) is not int or not 1 <= budget <= 4 or not callable(evaluate) or not callable(check_cancelled):
            raise ValueError('bounded tick and host cancellation required')
        with self._locked():
            return self._step_locked(evaluate, check_cancelled=check_cancelled, budget=budget)

    def _step_locked(self, evaluate, *, check_cancelled, budget, task_request_ref=None):
        """Caller must own the cooperative session lock for the entire tick."""
        from .branch_task_recovery import guard_unfinished_tasks
        guard_unfinished_tasks(self, task_request_ref)
        self._frame()
        check_cancelled()
        self._authorize()
        plan, done, pending = self._state()
        if plan is None:
            plan = self._put('plan.json', self.spec)
        self._project(done)
        for _ in range(budget):
            if pending is not None:
                break
            node = choose_branch(self.branches, done)
            if node is None:
                break
            check_cancelled()
            self._authorize()
            intent = self._intent(node, done, plan)
            intent_ref = self._put('intents/' + node.id + '.json', intent)
            # Persisted intent is the crash boundary, not permission to auto-retry.
            try:
                check_cancelled()
                self._authorize()
                evidence = self._evidence(evaluate(node.id, deepcopy(intent)))
                check_cancelled()
                self._authorize()
            except Exception as exc:
                self._put('failures/' + node.id + '.json',
                          {'schema': 'merlin-registry-branch-failure/1', 'intent_ref': intent_ref,
                           'error_class': type(exc).__name__, 'reconciliation_required': True,
                           'qualification': False, 'promotion_authority': False})
                raise
            outcome = {'schema': 'merlin-registry-branch-outcome/1', 'intent_ref': intent_ref,
                       'evidence': evidence, 'status': 'passed_local_check' if evidence['passed'] else 'failed_local_check',
                       'qualification': False, 'promotion_authority': False}
            ref = self._put('outcomes/' + node.id + '.json', outcome)
            done[node.id] = {'ref': ref, 'intent_ref': intent_ref, 'body': outcome,
                             'status': 'verified' if evidence['passed'] else 'failed'}
            self._project(done)
        return self._view(plan, done, pending)

    def snapshot(self, *, expected_state: Mapping[str, Any] | None = None):
        with self._locked():
            return self._snapshot_locked(expected_state=expected_state)

    def _snapshot_locked(self, *, expected_state=None):
        """Publish only while the caller owns the session lock."""
        self._authorize()
        view = self.status()
        if expected_state is not None and canonical(expected_state) != canonical(view):
            raise BranchSessionConflict('session advanced before exact snapshot publication')
        return self._put('snapshots/' + digest(view) + '.json', view)


def build_branch_research_executor(session: RegistryBranchSession, evaluate: Callable, *, budget: int = 1):
    """Bind one Hermes task to one immutable tick result in the canonical registry.

    Retries after result publication replay the original snapshot, even after a
    later task advances the session. An intent without a result fails closed:
    external reconciliation is required, not another implicit tick. This is
    cooperative host-owned code, not process isolation or exactly-once IO.
    """
    if not isinstance(session, RegistryBranchSession) or not callable(evaluate) or type(budget) is not int or not 1 <= budget <= 4:
        raise ValueError('canonical session, executor and bounded tick required')

    def output(state, ref):
        summary = ('Branch session requires reconciliation' if state['reconciliation_required'] else
                   'Branch session recorded %d local outcomes' % state['completed'])
        return {'existing_artifact_ref': ref, 'summary': summary, 'media_type': 'application/json',
                'metadata': {'artifact_schema': state['schema'], 'branch_state': state,
                             'tool_identity': session.spec['executor']['id'] + '@sha256:' + session.spec['executor']['sha256'],
                             'qualification': False, 'promotion_authority': False}}

    def replay(record, request_ref):
        if (not isinstance(record, dict) or set(record) != {'schema', 'request_ref', 'snapshot_ref'}
                or record['schema'] != 'merlin-branch-task-result/1'
                or canonical(record['request_ref']) != canonical(request_ref)):
            raise BranchSessionConflict('task result is not bound to the original request')
        ref = session._ref(record['snapshot_ref'])
        raw = session.registry.read_artifact_ref(ref, max_bytes=MAX_RECORD)['content']
        state = json.loads(raw)
        if (not isinstance(state, dict) or canonical(state).encode('utf-8') != raw
                or ref['logical_path'] != session.base + 'snapshots/' + digest(state) + '.json'
                or ref['version'] != 1):
            raise BranchSessionConflict('task snapshot identity differs')
        plan, done, pending = session._state()
        count = state.get('completed')
        if type(count) is not int or not 0 <= count <= len(done):
            raise BranchSessionConflict('task snapshot cursor differs')
        prefix = dict(list(done.items())[:count])
        old_pending = state.get('reconciliation_required')
        if old_pending is not None and old_pending != pending:
            raise BranchSessionConflict('task snapshot reconciliation state differs')
        if canonical(state) != canonical(session._view(plan, prefix, old_pending)):
            raise BranchSessionConflict('task snapshot lineage differs')
        session._project(prefix)
        return output(state, ref)

    def execute(task, context):
        if (not isinstance(task, Mapping) or task.get('stage') != 'research'
                or not isinstance(task.get('task_id'), str) or not task['task_id'].strip()
                or len(task['task_id']) > 2000 or task['task_id'] != context.task_id
                or session.frame_ref not in context.artifact_refs):
            raise ValueError('Hermes task and exact frame binding required')
        hypothesis_id = getattr(context, 'hypothesis_id', None)
        if (not isinstance(hypothesis_id, str) or not hypothesis_id.strip()
                or len(hypothesis_id) > 2000
                or ('hypothesis_id' in task and task['hypothesis_id'] != hypothesis_id)):
            raise ValueError('exact Hermes hypothesis binding required')
        refs = [session._ref(ref) for ref in context.artifact_refs]
        if 'artifact_refs' in task and task['artifact_refs'] != refs:
            raise ValueError('task and context input references differ')
        execution_key = 'hermes-task-handler:' + task['task_id']
        if getattr(context, 'idempotency_key', execution_key) != execution_key:
            raise ValueError('Hermes idempotency identity differs')
        request = {'schema': 'merlin-branch-task-request/1', 'task': deepcopy(dict(task)),
                   'hypothesis_id': hypothesis_id, 'artifact_refs': refs,
                   'session_plan': deepcopy(session.spec), 'branch_budget': budget,
                   'qualification': False, 'promotion_authority': False}
        if len(canonical(request).encode('utf-8')) > MAX_RECORD:
            raise ValueError('bounded task binding required')
        # Project-global task identity also rejects reuse for a different session.
        path = 'branch-research-tasks/' + digest(execution_key) + '/'
        with session._locked():
            session._frame()
            context.check_cancelled()
            session._authorize()
            prior = session._read_path(path + 'request.json')
            result = session._read_path(path + 'result.json')
            if prior is not None:
                if canonical(prior[0]) != canonical(request):
                    raise BranchSessionConflict('task identity reused with different inputs')
                if result is None:
                    raise BranchSessionConflict('interrupted task requires reconciliation before retry')
                answer = replay(result[0], prior[1])
            else:
                if result is not None:
                    raise BranchSessionConflict('orphan task result')
                from .branch_task_recovery import guard_unfinished_tasks
                guard_unfinished_tasks(session)
                request_ref = session._put_path(path + 'request.json', request)
                state = session._step_locked(evaluate, check_cancelled=context.check_cancelled,
                                             budget=budget, task_request_ref=request_ref)
                context.check_cancelled()
                session._authorize()
                ref = session._snapshot_locked(expected_state=state)
                context.check_cancelled()
                session._authorize()
                session._put_path(path + 'result.json',
                                  {'schema': 'merlin-branch-task-result/1', 'request_ref': request_ref,
                                   'snapshot_ref': ref})
                answer = output(state, ref)
            context.check_cancelled()
            session._authorize()
            return answer
    return execute
