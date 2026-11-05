"""Approval/MCFC-gated recovery orchestration over Hermes, CACE and HUD telemetry.

All recovered files land in a unique quarantine namespace. Promotion is a separate
human-approved operation and is intentionally not implemented here.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from merlin.change_manifest import (
    build_change_manifest, create_recovery_snapshot, validate_change_manifest,
)
from merlin.hermes_outbox import HermesOutboxConsumer
from merlin.recovery_adapters import (
    GitRecoveryAdapter, RegistryRecoveryAdapter, ZipRecoveryAdapter,
)
from merlin.telemetry import agent_event_sink


def mcfc_lease_validator(lease_book, *, clock: Callable[[], datetime] | None = None):
    """Adapt the canonical MCFC LeaseBook to the recovery coordinator contract."""
    def validate(lease_ref: str, budget: Mapping[str, int]) -> bool:
        now = (clock or (lambda: datetime.now(timezone.utc)))()
        try:
            lease = lease_book.get(lease_ref)
            if not lease_book.validate_start(lease_ref, now=now):
                return False
            return bool(
                budget.get("cpu_cores", 0) <= lease.resources.cpu_cores
                and budget.get("memory_bytes", 0) <= lease.resources.memory_bytes
                and budget.get("max_wall_seconds", 0) <= lease.max_wall_seconds
                and budget.get("compute_budget_units", 0) <= lease.compute_budget_units
                and lease.promotion_authority is False
                and lease.authority == "execution_only"
            )
        except (KeyError, ValueError, TypeError):
            return False
    return validate


class AvreaRecoveryAdapter:
    """Recover retained artifacts from a previously accepted Avrea job receipt."""
    def __init__(self, avrea_adapter):
        self.avrea = avrea_adapter

    def recover(self, *, job_id: str, project_id: str, expected_sha256: str,
                artifact_name: str) -> dict[str, Any]:
        result = self.avrea.collect(job_id, project_id=project_id, logical_prefix="_avrea-recovery-source")
        matches = [item for item in result["artifacts"]
                   if item["name"] == artifact_name and item["sha256"] == expected_sha256]
        if len(matches) != 1:
            raise KeyError("retained Avrea artifact is missing or ambiguous")
        data = self.avrea.registry.get_artifact_bytes(matches[0]["sha256"])
        recovery_path = "_recovery/avrea/" + job_id + "/" + artifact_name
        digest = self.avrea.registry.put_artifact(
            project_id, recovery_path, data, actor="avrea-recovery",
            operation_id="avrea:" + job_id,
        )
        if digest != expected_sha256 or not self.avrea.registry.verify_artifact(digest):
            raise ValueError("Avrea recovered bytes failed exact digest verification")
        return {"confidence": "exact", "source": "avrea", "job_id": job_id,
                "original_path": artifact_name, "recovery_path": recovery_path,
                "sha256": digest, "size_bytes": len(data)}


class RecoveryCoordinator:
    """Queue and execute exact-byte recoveries through the durable Hermes outbox."""
    TOPIC = "merlin.hermes.recovery"

    def __init__(self, *, registry, outbox,
                 approval_validator: Callable[[str, Mapping[str, Any]], bool],
                 lease_validator: Callable[[str, Mapping[str, int]], bool],
                 repository: str, requester_id: str,
                 git_repository: str | Path | None = None,
                 cace_adapter=None, avrea_adapter=None):
        if not callable(approval_validator) or not callable(lease_validator):
            raise ValueError("approval and MCFC lease validators are required")
        if not repository or "/" not in repository or not requester_id.strip():
            raise ValueError("repository and requester identity are required")
        self.registry = registry
        self.outbox = outbox
        self.approval_validator = approval_validator
        self.lease_validator = lease_validator
        self.repository = repository
        self.requester_id = requester_id
        self.git_repository = Path(git_repository).resolve() if git_repository is not None else None
        self.cace = cace_adapter
        self.avrea = AvreaRecoveryAdapter(avrea_adapter) if avrea_adapter is not None else None
        self.hermes_events = agent_event_sink(outbox, "hermes")
        self.consumer = HermesOutboxConsumer(outbox)

    def request(self, *, task_id: str, project_id: str, source: str,
                expected_sha256: str, original_path: str,
                approval_ref: str, lease_ref: str, resource_budget: Mapping[str, int],
                commit_sha: str | None = None, archive_path: str | None = None,
                job_id: str | None = None, actor: str | None = None) -> dict[str, Any]:
        payload = {
            "schema": "merlin-recovery-task/1", "task_id": task_id,
            "project_id": project_id, "source": source,
            "expected_sha256": expected_sha256, "original_path": original_path,
            "approval_ref": approval_ref, "lease_ref": lease_ref,
            "resource_budget": dict(resource_budget), "commit_sha": commit_sha,
            "archive_path": archive_path, "job_id": job_id,
            "actor": actor or self.requester_id,
        }
        if not task_id.strip() or not project_id.strip() or not original_path.strip():
            raise ValueError("task, project and original path are required")
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
            raise ValueError("expected_sha256 must be lowercase SHA-256")
        if source not in {"git", "zip", "registry", "avrea"}:
            raise ValueError("unsupported recovery source")
        required = {"cpu_cores", "memory_bytes", "max_wall_seconds", "compute_budget_units"}
        if not required.issubset(payload["resource_budget"]):
            raise ValueError("MCFC resource budget is incomplete")
        if any(isinstance(v, bool) or not isinstance(v, int) or v <= 0
               for v in payload["resource_budget"].values()):
            raise ValueError("MCFC resource budget values must be positive integers")
        if not self.approval_validator(approval_ref, payload):
            raise PermissionError("explicit recovery approval was not validated")
        if not self.lease_validator(lease_ref, payload["resource_budget"]):
            raise PermissionError("active MCFC recovery lease was not validated")
        if source == "git" and (
            not commit_sha or len(commit_sha) != 40 or self.git_repository is None
        ):
            raise ValueError("Git recovery requires a pinned commit and configured repository root")
        if source == "zip" and not archive_path:
            raise ValueError("ZIP recovery requires an archive path accessible to the worker")
        if source == "avrea" and (not job_id or self.avrea is None):
            raise ValueError("Avrea recovery requires a configured adapter and retained job ID")
        if self.cace is not None and (
            not commit_sha or len(commit_sha) != 40
        ):
            raise ValueError("CACE qualification requires an exact source commit binding")
        key = "merlin-recovery:" + task_id
        queued = self.outbox.enqueue(key, self.TOPIC, payload)
        self.hermes_events(
            kind="task.started", run_id=task_id, task_id=task_id,
            payload={"agent_id": "hermes", "role": "recovery orchestrator",
                     "status": "queued", "activity": "approved recovery queued",
                     "source": source, "expected_sha256": expected_sha256},
            evidence_refs=["sha256:" + expected_sha256],
        )
        return {"event_id": queued["event_id"], "task_id": task_id, "state": queued["state"]}

    def _execute(self, event: Mapping[str, Any]) -> dict[str, Any]:
        payload = event.get("payload")
        if not isinstance(payload, Mapping) or payload.get("schema") != "merlin-recovery-task/1":
            raise ValueError("invalid Hermes recovery event")
        if not self.approval_validator(payload["approval_ref"], payload):
            raise PermissionError("recovery approval expired or was revoked")
        if not self.lease_validator(payload["lease_ref"], payload["resource_budget"]):
            raise PermissionError("MCFC recovery lease expired or was revoked")

        project_id = payload["project_id"]
        snapshot = create_recovery_snapshot(
            self.registry, project_id, actor="pre-recovery:" + payload["task_id"]
        )
        source = payload["source"]
        common = {"expected_sha256": payload["expected_sha256"], "project_id": project_id}
        if source == "registry":
            result = RegistryRecoveryAdapter(self.registry).recover(
                digest=payload["expected_sha256"], project_id=project_id,
                original_path=payload["original_path"])
        elif source == "git":
            result = GitRecoveryAdapter(self.git_repository).recover(
                commit=payload["commit_sha"], path=payload["original_path"],
                registry=self.registry, **common)
        elif source == "zip":
            result = ZipRecoveryAdapter().recover(
                archive_path=payload["archive_path"], member_path=payload["original_path"],
                registry=self.registry, **common)
        elif source == "avrea" and self.avrea is not None:
            result = self.avrea.recover(
                job_id=payload["job_id"], project_id=project_id,
                expected_sha256=payload["expected_sha256"],
                artifact_name=payload["original_path"])
        else:
            raise ValueError("recovery source is not configured")

        status = "quarantined_unverified"
        cace_result = None
        if self.cace is not None:
            cace_result = self.cace.verify_artifact(
                project_id=project_id, repository=self.repository,
                commit_sha=payload["commit_sha"],
                artifact_sha256=result["sha256"], artifact_kind="recovered_artifact",
                artifact_schema="merlin-recovery-artifact/1",
                requester_id=self.requester_id, logical_path=result["recovery_path"],
            )
            cace_status = cace_result.get("verification_status")
            if cace_status == "verified":
                status = "quarantined_independently_verified"
            elif cace_status == "rejected":
                status = "quarantined_cace_rejected"
            elif cace_status == "inconclusive":
                status = "quarantined_cace_inconclusive"
            else:
                raise ValueError("CACE returned an unsupported recovery verification status")

        after_snapshot = create_recovery_snapshot(
            self.registry, project_id, actor="post-recovery:" + payload["task_id"]
        )
        change_manifest = build_change_manifest(
            snapshot["manifest"], after_snapshot["manifest"],
            operation_id=payload["task_id"], actor=payload["actor"],
            reason="recover exact bytes into quarantine without replacing canonical path",
        )
        validate_change_manifest(change_manifest)

        receipt = {
            "schema": "merlin-recovery-result/1",
            "task_id": payload["task_id"], "status": status,
            "source": source, **result,
            "pre_recovery_snapshot": snapshot["recovery_id"],
            "pre_recovery_manifest_sha256": snapshot["manifest_digest"],
            "post_recovery_snapshot": after_snapshot["recovery_id"],
            "post_recovery_manifest_sha256": after_snapshot["manifest_digest"],
            "change_manifest": change_manifest,
            "cace_receipt_sha256": (cace_result or {}).get("receipt_artifact_sha256"),
            "promotion_authority": False,
        }
        receipt["receipt_sha256"] = hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.hermes_events(
            kind="artifact.registered", run_id=payload["task_id"], task_id=payload["task_id"],
            payload={"agent_id": "hermes", "role": "recovery orchestrator",
                     "status": status, "activity": "artifact recovered to quarantine",
                     "recovery_path": result["recovery_path"], "sha256": result["sha256"]},
            evidence_refs=["sha256:" + result["sha256"]],
        )
        self.hermes_events(
            kind="task.completed", run_id=payload["task_id"], task_id=payload["task_id"],
            payload={"agent_id": "hermes", "role": "recovery orchestrator",
                     "status": status, "summary": "recovery completed without canonical overwrite"},
            evidence_refs=["sha256:" + result["sha256"]],
        )
        return receipt

    def consume_one(self, worker_id: str = "hermes-recovery") -> dict[str, Any] | None:
        return self.consumer.consume_one(
            worker_id, self._execute, topics=(self.TOPIC,), lease_seconds=120,
            retry_delay_seconds=5, max_attempts=3,
        )
