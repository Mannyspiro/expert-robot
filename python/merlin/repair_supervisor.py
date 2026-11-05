"""Bounded autonomous repair: diagnose/build/test candidates, never mutate canonical paths.

The builder and test runner are injected domain services. A candidate is eligible
for a draft PR only after CACE independently verifies every exact artifact.
Merge, deployment, deletion and canonical promotion are deliberately absent.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping

from merlin.change_manifest import (
    build_change_manifest, create_recovery_snapshot, validate_change_manifest,
)
from merlin.hermes_outbox import HermesOutboxConsumer
from merlin.telemetry import agent_event_sink


def avrea_repair_test_runner(avrea_adapter, *, job_factory, result_evaluator):
    """Build a test runner around the existing AvreaAdapter without inventing result semantics.

    job_factory receives candidate refs and the full approved task payload. The
    evaluator must inspect collected artifacts and return a mapping containing
    passed=True only when the actual test evidence supports that conclusion.
    """
    if not callable(job_factory) or not callable(result_evaluator):
        raise ValueError("Avrea job_factory and result_evaluator are required")

    def run(candidate_refs, task_payload):
        job = job_factory(candidate_refs, task_payload)
        dispatch = avrea_adapter.dispatch(job)
        collected = avrea_adapter.collect(
            dispatch["job_id"], project_id=task_payload["project_id"],
            logical_prefix="_repair-avrea-results",
        )
        evaluated = result_evaluator(collected, candidate_refs, task_payload)
        if not isinstance(evaluated, Mapping):
            raise TypeError("Avrea result evaluator must return a mapping")
        return dict(evaluated)

    return run


def _safe_segment(value: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not segment or segment in {".", ".."}:
        raise ValueError("repair identity cannot form a safe candidate path")
    return segment[:120]


class RepairSupervisor:
    TOPIC = "merlin.hermes.repair"

    def __init__(self, *, registry, outbox,
                 candidate_builder: Callable[[Mapping[str, Any]], Mapping[str, Any]],
                 test_runner: Callable[[list[dict[str, Any]], Mapping[str, int]], Mapping[str, Any]],
                 approval_validator: Callable[[str, Mapping[str, Any]], bool],
                 lease_validator: Callable[[str, Mapping[str, int]], bool],
                 repository: str, requester_id: str, cace_adapter=None,
                 draft_pr_publisher: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None):
        for fn, label in ((candidate_builder, "candidate_builder"),
                          (test_runner, "test_runner"),
                          (approval_validator, "approval_validator"),
                          (lease_validator, "lease_validator")):
            if not callable(fn):
                raise ValueError(label + " must be an injected callable")
        if not repository or "/" not in repository or not requester_id.strip():
            raise ValueError("repository and requester identity are required")
        self.registry = registry
        self.outbox = outbox
        self.builder = candidate_builder
        self.test_runner = test_runner
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.repository = repository
        self.requester_id = requester_id
        self.cace = cace_adapter
        self.draft_pr_publisher = draft_pr_publisher
        self.events = agent_event_sink(outbox, "hermes")
        self.consumer = HermesOutboxConsumer(outbox)

    def observe_failure(self, event: Mapping[str, Any], *, project_id: str,
                        commit_sha: str, approval_ref: str, lease_ref: str,
                        resource_budget: Mapping[str, int]) -> dict[str, Any] | None:
        """Turn a normalized, observable failure into a bounded repair candidate task."""
        kind = event.get("kind")
        payload = event.get("payload", {})
        is_failure = (
            kind == "system.error"
            or (kind == "verification.completed" and payload.get("status") in {"rejected", "inconclusive"})
            or (kind == "task.completed" and payload.get("status") in {"failed", "error"})
        )
        if not is_failure:
            return None
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("failure event requires a stable event_id")
        task_id = "repair-" + hashlib.sha256(event_id.encode()).hexdigest()[:24]
        return self.submit(
            task_id=task_id, project_id=project_id, commit_sha=commit_sha,
            failure_event=dict(event), approval_ref=approval_ref,
            lease_ref=lease_ref, resource_budget=resource_budget,
        )

    def submit(self, *, task_id: str, project_id: str, commit_sha: str,
               failure_event: Mapping[str, Any], approval_ref: str, lease_ref: str,
               resource_budget: Mapping[str, int]) -> dict[str, Any]:
        if not task_id.strip() or not project_id.strip():
            raise ValueError("task_id and project_id are required")
        if len(commit_sha) != 40 or any(c not in "0123456789abcdef" for c in commit_sha):
            raise ValueError("repair requires an exact lowercase commit SHA")
        required = {"cpu_cores", "memory_bytes", "max_wall_seconds", "compute_budget_units"}
        budget = dict(resource_budget)
        if not required.issubset(budget) or any(
            isinstance(v, bool) or not isinstance(v, int) or v <= 0 for v in budget.values()
        ):
            raise ValueError("repair resource budget is incomplete or invalid")
        payload = {
            "schema": "merlin-repair-task/1", "task_id": task_id,
            "project_id": project_id, "commit_sha": commit_sha,
            "failure_event": dict(failure_event),
            "approval_ref": approval_ref, "lease_ref": lease_ref,
            "resource_budget": budget, "requester_id": self.requester_id,
            "promotion_authority": False,
        }
        if not self.approval_validator(approval_ref, payload):
            raise PermissionError("explicit repair approval was not validated")
        if not self.lease_validator(lease_ref, budget):
            raise PermissionError("active MCFC repair lease was not validated")
        queued = self.outbox.enqueue("merlin-repair:" + task_id, self.TOPIC, payload)
        self.events(
            kind="task.started", run_id=task_id, task_id=task_id,
            payload={"agent_id": "hermes", "role": "repair supervisor",
                     "status": "queued", "activity": "bounded repair candidate queued"},
        )
        return {"task_id": task_id, "event_id": queued["event_id"], "state": queued["state"]}

    def _execute(self, event: Mapping[str, Any]) -> dict[str, Any]:
        payload = event.get("payload")
        if not isinstance(payload, Mapping) or payload.get("schema") != "merlin-repair-task/1":
            raise ValueError("invalid Hermes repair event")
        if not self.approval_validator(payload["approval_ref"], payload):
            raise PermissionError("repair approval expired or was revoked")
        if not self.lease_validator(payload["lease_ref"], payload["resource_budget"]):
            raise PermissionError("MCFC repair lease expired or was revoked")

        project_id, task_id = payload["project_id"], payload["task_id"]
        before = create_recovery_snapshot(self.registry, project_id, actor="pre-repair:" + task_id)
        proposed = self.builder(payload)
        if not isinstance(proposed, Mapping) or not isinstance(proposed.get("files"), list) or not proposed["files"]:
            raise ValueError("repair builder must return a non-empty files list")
        candidate_refs = []
        prefix = "_repair-candidates/" + _safe_segment(task_id)
        for item in proposed["files"]:
            if not isinstance(item, Mapping):
                raise ValueError("repair file entry must be an object")
            path, data = item.get("path"), item.get("content")
            if not isinstance(path, str) or not isinstance(data, bytes):
                raise ValueError("repair candidate requires a relative path and raw bytes")
            safe_path = _safe_segment(path.replace("/", "-").replace("\\", "-"))
            media_type = item.get("media_type", "application/octet-stream")
            logical_path = prefix + "/" + safe_path
            digest = self.registry.put_artifact(
                project_id, logical_path, data, media_type,
                actor="merlin-repair", operation_id=task_id,
            )
            candidate_refs.append({
                "path": path, "candidate_path": logical_path,
                "sha256": digest, "size_bytes": len(data),
            })

        test_result = self.test_runner(candidate_refs, payload)
        if not isinstance(test_result, Mapping) or test_result.get("passed") is not True:
            status = "candidate_rejected"
            cace_receipts = []
        else:
            status = "candidate_tested_unverified"
            cace_receipts = []
            if self.cace is not None:
                for item in candidate_refs:
                    receipt = self.cace.verify_artifact(
                        project_id=project_id, repository=self.repository,
                        commit_sha=payload["commit_sha"],
                        artifact_sha256=item["sha256"], artifact_kind="repair_candidate",
                        artifact_schema="merlin-repair-candidate/1",
                        requester_id=self.requester_id, logical_path=item["candidate_path"],
                    )
                    cace_receipts.append(receipt)
                states = {item.get("verification_status") for item in cace_receipts}
                if cace_receipts and states == {"verified"}:
                    status = "candidate_independently_verified"
                elif "rejected" in states:
                    status = "candidate_cace_rejected"
                elif "inconclusive" in states:
                    status = "candidate_cace_inconclusive"

        after = create_recovery_snapshot(self.registry, project_id, actor="post-repair:" + task_id)
        change_manifest = build_change_manifest(
            before["manifest"], after["manifest"], operation_id=task_id,
            actor=self.requester_id,
            reason="isolated repair candidate; canonical artifact heads unchanged",
        )
        validate_change_manifest(change_manifest)
        pr_result = None
        if status == "candidate_independently_verified" and self.draft_pr_publisher is not None:
            pr_result = self.draft_pr_publisher({
                "task_id": task_id, "project_id": project_id,
                "commit_sha": payload["commit_sha"],
                "candidate_refs": candidate_refs,
                "test_result": dict(test_result),
                "cace_receipts": cace_receipts,
                "change_manifest": change_manifest,
                "draft_only": True,
                "merge_authority": False,
            })

        result = {
            "schema": "merlin-repair-result/1", "task_id": task_id,
            "status": status, "candidate_refs": candidate_refs,
            "test_result": dict(test_result),
            "cace_receipts": cace_receipts,
            "pre_repair_snapshot": before["recovery_id"],
            "post_repair_snapshot": after["recovery_id"],
            "change_manifest": change_manifest,
            "draft_pr": dict(pr_result) if isinstance(pr_result, Mapping) else None,
            "canonical_mutation": False, "promotion_authority": False,
        }
        result["receipt_sha256"] = hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        self.events(
            kind="artifact.registered", run_id=task_id, task_id=task_id,
            payload={"agent_id": "hermes", "role": "repair supervisor",
                     "status": status, "activity": "repair candidate retained without promotion",
                     "candidate_count": len(candidate_refs)},
            evidence_refs=["sha256:" + item["sha256"] for item in candidate_refs],
        )
        self.events(
            kind="task.completed", run_id=task_id, task_id=task_id,
            payload={"agent_id": "hermes", "role": "repair supervisor",
                     "status": status, "summary": "candidate preserved; canonical files unchanged"},
            evidence_refs=["sha256:" + item["sha256"] for item in candidate_refs],
        )
        return result

    def consume_one(self, worker_id: str = "hermes-repair", *,
                    now: float | None = None) -> dict[str, Any] | None:
        """Consume one repair event; optional clock injection supports deterministic fault drills."""
        return self.consumer.consume_one(
            worker_id, self._execute, topics=(self.TOPIC,), lease_seconds=180,
            retry_delay_seconds=10, max_attempts=3, now=now,
        )
