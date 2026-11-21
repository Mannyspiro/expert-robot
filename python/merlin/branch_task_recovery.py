"""Host-authorized reconciliation of canonical task checkpoints, never external IO.

All records reuse MerlinRegistry and its exact ArtifactRefs. The cooperative
workflow lock is not a security boundary against trusted code bypassing it.
An outcome missing after intent remains ambiguous: this module never fabricates
it, calls a provider to repeat it, or grants promotion authority.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable, Mapping

from .branch_research import canonical, digest
from .branch_registry import BranchSessionConflict, MAX_RECORD, RegistryBranchSession

TASK_PREFIX = "branch-research-tasks/"
MAX_TASK_REQUESTS = 1024


def task_path(task_id: str) -> str:
    return TASK_PREFIX + digest("hermes-task-handler:" + task_id) + "/"


def _same(a: Any, b: Any) -> bool:
    return canonical(a) == canonical(b)


def _snapshot_state(session: RegistryBranchSession, ref: Mapping[str, Any]) -> dict:
    ref = session._ref(ref)
    raw = session.registry.read_artifact_ref(ref, max_bytes=MAX_RECORD)["content"]
    state = json.loads(raw)
    if (not isinstance(state, dict) or canonical(state).encode("utf-8") != raw
            or ref["version"] != 1
            or ref["logical_path"] != session.base + "snapshots/" + digest(state) + ".json"):
        raise BranchSessionConflict("task snapshot identity differs")
    _validate_view(session, state)
    return state


def _validate_view(session: RegistryBranchSession, state: Mapping[str, Any]) -> None:
    plan, done, pending = session._state()
    count = state.get("completed")
    if type(count) is not int or not 0 <= count <= len(done):
        raise BranchSessionConflict("task snapshot cursor differs")
    prefix = dict(list(done.items())[:count])
    old_pending = state.get("reconciliation_required")
    if old_pending is not None and old_pending != pending:
        raise BranchSessionConflict("task snapshot reconciliation state differs")
    if not _same(state, session._view(plan, prefix, old_pending)):
        raise BranchSessionConflict("task snapshot lineage differs")


def guard_unfinished_tasks(session: RegistryBranchSession, active_ref=None) -> None:
    """Fence all cooperative entry points, including legacy/direct session ticks."""
    found = session.registry.artifact_paths(session.project_id, prefix=TASK_PREFIX,
                                            suffix="/request.json", limit=MAX_TASK_REQUESTS)
    if found["truncated"]:
        raise BranchSessionConflict("task history inspection ceiling reached; archival review required")
    for path in found["paths"]:
        request, ref = session._read_path(path)
        schema = request.get("schema")
        if schema not in {"merlin-branch-task-request/1", "merlin-branch-task-request/2"}:
            raise BranchSessionConflict("unsupported canonical task request schema")
        identity = request.get("identity") if schema == "merlin-branch-task-request/2" else request
        if not isinstance(identity, dict) or not isinstance(identity.get("session_plan"), dict):
            raise BranchSessionConflict("malformed canonical task request")
        plan = identity["session_plan"]
        if plan.get("session_id") != session.session_id:
            continue
        if not _same(plan, session.spec):
            raise BranchSessionConflict("task reservation binds a different session plan")
        result = session._read_path(path[:-len("request.json")] + "result.json")
        if result is None:
            if active_ref is None or not _same(active_ref, ref):
                raise BranchSessionConflict("unfinished session task requires reconciliation")
        else:
            body = result[0]
            if (body.get("schema") not in {"merlin-branch-task-result/1", "merlin-branch-task-result/2"}
                    or not _same(body.get("request_ref"), ref)):
                raise BranchSessionConflict("task result is not bound to its reservation")
            _snapshot_state(session, body["snapshot_ref"])


class RecoverableBranchExecutor:
    """Opt-in Hermes executor with task ownership and separately approved recovery.

    recovery_authorizer is host-injected and must authenticate/authorize the exact
    decision ArtifactRef. A structurally valid decision or hash is NOT approval.
    No endpoint is added and no callback is inferred from task-supplied data.
    """

    def __init__(self, session: RegistryBranchSession, evaluate: Callable, *, budget: int = 1,
                 recovery_authorizer: Callable | None = None):
        if (not isinstance(session, RegistryBranchSession) or not callable(evaluate)
                or type(budget) is not int or not 1 <= budget <= 4
                or (recovery_authorizer is not None and not callable(recovery_authorizer))):
            raise ValueError("canonical session, bounded executor and optional host recovery authority required")
        self.session, self.evaluate, self.budget = session, evaluate, budget
        self.recovery_authorizer = recovery_authorizer

    def _identity(self, task, context):
        from .hermes_worker import HermesWorker
        task = deepcopy(dict(task)) if isinstance(task, Mapping) else task
        HermesWorker._validate_payload(task)
        if (task["stage"] != "research" or task["task_id"] != context.task_id
                or task["hypothesis_id"] != context.hypothesis_id
                or not _same(task["artifact_refs"], list(context.artifact_refs))
                or not _same(task["resource_budget"], dict(context.resource_budget))
                or task["approval_ref"] != context.approval_ref or task["lease_ref"] != context.lease_ref
                or context.idempotency_key != "hermes-task-handler:" + task["task_id"]
                or not any(_same(self.session.frame_ref, ref) for ref in context.artifact_refs)):
            raise ValueError("exact admitted Hermes task/context binding required")
        refs = [self.session._ref(ref) for ref in context.artifact_refs]
        for ref in refs:
            self.session.registry.read_artifact_ref(ref, max_bytes=2 * 1024 * 1024)
        return {"task": task, "hypothesis_id": context.hypothesis_id, "artifact_refs": refs,
                "session_plan": deepcopy(self.session.spec), "branch_budget": self.budget,
                "qualification": False, "promotion_authority": False}

    def _gate(self, context):
        self.session._frame()
        context.check_cancelled()
        self.session._authorize()

    def _request(self, identity, path):
        saved = self.session._read_path(path + "request.json")
        if saved is None:
            raise BranchSessionConflict("task request missing")
        body, ref = saved
        if (set(body) != {"schema", "identity", "starting_state"}
                or body["schema"] != "merlin-branch-task-request/2"
                or not _same(body["identity"], identity)):
            raise BranchSessionConflict("task inputs changed or legacy request lacks a recoverable start")
        _validate_view(self.session, body["starting_state"])
        if body["starting_state"]["reconciliation_required"] is not None:
            raise BranchSessionConflict("task began with ambiguous branch intent")
        return body, ref

    def _transition(self, request, state):
        _validate_view(self.session, state)
        start = request["starting_state"]
        before, after = start["completed"], state["completed"]
        if (state["reconciliation_required"] is not None or not before <= after <= before + self.budget
                or not _same(state["outcome_refs"][:before], start["outcome_refs"])):
            raise BranchSessionConflict("ambiguous effect or task outcome range differs")
        return after - before

    def _answer(self, state, ref, recovery_ref):
        return {"existing_artifact_ref": ref,
                "summary": "Branch task recorded %d local outcomes" % state["completed"],
                "media_type": "application/json",
                "metadata": {"artifact_schema": state["schema"], "branch_state": state,
                             "task_recovery_ref": recovery_ref,
                             "tool_identity": self.session.spec["executor"]["id"] + "@sha256:" +
                                              self.session.spec["executor"]["sha256"],
                             "qualification": False, "promotion_authority": False}}

    def _replay(self, request, request_ref, result):
        if (set(result) != {"schema", "request_ref", "snapshot_ref", "recovery_ref"}
                or result["schema"] != "merlin-branch-task-result/2"
                or not _same(result["request_ref"], request_ref)):
            raise BranchSessionConflict("task result binding differs")
        state = _snapshot_state(self.session, result["snapshot_ref"])
        self._transition(request, state)
        recovery_ref = result["recovery_ref"]
        if recovery_ref is not None:
            path = task_path(request["identity"]["task"]["task_id"])
            recovery = self.session._read_path(path + "recovery.json")
            if (recovery is None or not _same(recovery[1], recovery_ref)
                    or not _same(recovery[0]["request_ref"], request_ref)
                    or recovery[0]["state_sha256"] != digest(state)):
                raise BranchSessionConflict("task recovery binding differs")
            self.session.registry.read_artifact_ref(recovery[0]["decision_ref"], max_bytes=MAX_RECORD)
        _, done, _ = self.session._state()
        self.session._project(dict(list(done.items())[:state["completed"]]))
        return self._answer(state, result["snapshot_ref"], recovery_ref)

    def _publish(self, path, request, request_ref, state, context, recovery_ref=None):
        self._transition(request, state)
        self._gate(context)
        ref = self.session._snapshot_locked(expected_state=state)
        self._gate(context)
        result = {"schema": "merlin-branch-task-result/2", "request_ref": request_ref,
                  "snapshot_ref": ref, "recovery_ref": recovery_ref}
        self.session._put_path(path + "result.json", result)
        answer = self._replay(request, request_ref, result)
        self._gate(context)
        return answer

    def __call__(self, task, context):
        identity = self._identity(task, context)
        path = task_path(context.task_id)
        with self.session._locked():
            self._gate(context)
            prior = self.session._read_path(path + "request.json")
            if prior is not None:
                request, request_ref = self._request(identity, path)
                result = self.session._read_path(path + "result.json")
                if result is None:
                    raise BranchSessionConflict("interrupted task requires explicit reconciliation")
                answer = self._replay(request, request_ref, result[0])
                self._gate(context)
                return answer
            if self.session._read_path(path + "result.json") is not None:
                raise BranchSessionConflict("orphan task result")
            guard_unfinished_tasks(self.session)
            plan, done, pending = self.session._state()
            if pending is not None:
                raise BranchSessionConflict("branch has an unresolved external-effect intent")
            if plan is None:
                plan = self.session._put("plan.json", self.session.spec)
            request = {"schema": "merlin-branch-task-request/2", "identity": identity,
                       "starting_state": self.session._view(plan, done, None)}
            request_ref = self.session._put_path(path + "request.json", request)
            state = self.session._step_locked(self.evaluate, check_cancelled=context.check_cancelled,
                                              budget=self.budget, task_request_ref=request_ref)
            return self._publish(path, request, request_ref, state, context)

    def reconcile(self, task, context, *, decision_ref):
        """Publish committed outcomes, or close a proven no-execution tick.

        A branch intent without outcome remains blocked. Provider-specific
        external-effect reconciliation is deliberately not inferred here.
        """
        if self.recovery_authorizer is None:
            raise PermissionError("separately provisioned recovery authority required")
        identity = self._identity(task, context)
        path = task_path(context.task_id)
        with self.session._locked():
            self._gate(context)
            request, request_ref = self._request(identity, path)
            decision_ref = self.session._ref(decision_ref)
            raw = self.session.registry.read_artifact_ref(decision_ref, max_bytes=MAX_RECORD)["content"]
            decision = json.loads(raw)
            keys = {"schema", "request_ref", "expected_state_sha256", "action", "reviewer_id", "reason",
                    "authority", "qualification", "promotion_authority"}
            if (not isinstance(decision, dict) or set(decision) != keys
                    or canonical(decision).encode("utf-8") != raw
                    or decision["schema"] != "merlin-branch-recovery-decision/1"
                    or not _same(decision["request_ref"], request_ref)
                    or decision["action"] not in {"publish_committed_outcomes_only", "close_without_execution"}
                    or decision["authority"] != "reconcile_only"
                    or decision["qualification"] is not False or decision["promotion_authority"] is not False
                    or any(not isinstance(decision[k], str) or not decision[k].strip() or len(decision[k]) > 2000
                           for k in ("reviewer_id", "reason"))):
                raise ValueError("bounded exact-request recovery decision required")
            if self.recovery_authorizer(deepcopy(decision_ref), deepcopy(decision)) is not True:
                raise PermissionError("recovery decision not authorized by host")
            self._gate(context)
            prior_result = self.session._read_path(path + "result.json")
            prior_recovery = self.session._read_path(path + "recovery.json")
            if prior_recovery and not _same(prior_recovery[0]["decision_ref"], decision_ref):
                raise BranchSessionConflict("a different recovery decision is already bound")
            if prior_result:
                if prior_recovery is None:
                    raise BranchSessionConflict("task was completed without recovery")
                answer = self._replay(request, request_ref, prior_result[0])
                self._gate(context)
                return answer
            guard_unfinished_tasks(self.session, request_ref)
            state = self.session.status()
            if digest(state) != decision["expected_state_sha256"]:
                raise BranchSessionConflict("recovery decision is stale")
            delta = self._transition(request, state)
            if ((decision["action"] == "publish_committed_outcomes_only" and delta < 1)
                    or (decision["action"] == "close_without_execution" and delta != 0)):
                raise BranchSessionConflict("recovery action does not match committed outcome count")
            recovery_ref = self.session._put_path(path + "recovery.json", {
                "schema": "merlin-branch-task-recovery/1", "request_ref": request_ref,
                "decision_ref": decision_ref, "state_sha256": digest(state),
                "action": decision["action"], "evaluator_reexecuted": False,
                "qualification": False, "promotion_authority": False})
            return self._publish(path, request, request_ref, state, context, recovery_ref)
