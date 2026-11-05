"""Canonical before/after change manifests and pre-change recovery snapshots."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def create_recovery_snapshot(registry, project_id: str, *, actor: str = "merlin") -> dict[str, Any]:
    """Verify every current blob and persist a complete, content-addressed inventory."""
    inventory = registry.inventory(project_id)
    entries = []
    for item in inventory["artifacts"]:
        content = registry.get_artifact_bytes(item["digest"])
        entries.append({
            "path": item["logical_path"],
            "sha256": item["digest"],
            "size_bytes": len(content),
            "media_type": item["media_type"],
            "generation": item.get("generation", 1),
            "disposition": "retained",
        })
    manifest = {
        "schema": "merlin-recovery-manifest/1",
        "project_id": project_id,
        "project_name": inventory["name"],
        "project_version": inventory["version"],
        "artifacts": entries,
    }
    recovery_id = "rp_" + uuid4().hex
    digest = registry.add_recovery_point(recovery_id, project_id, manifest, actor=actor)
    return {"recovery_id": recovery_id, "manifest_digest": digest, "manifest": manifest}


def build_change_manifest(before: dict[str, Any], after: dict[str, Any],
                          *, operation_id: str, actor: str, reason: str) -> dict[str, Any]:
    """Build a complete path-level diff; deletions are always unresolved by default."""
    if not operation_id.strip() or not actor.strip() or not reason.strip():
        raise ValueError("operation_id, actor and reason are required")

    def indexed(snapshot):
        result = {}
        for item in snapshot.get("artifacts", []):
            path = item.get("path")
            if not isinstance(path, str) or not path or path in result:
                raise ValueError("snapshot contains a missing or duplicate artifact path")
            if not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64:
                raise ValueError("snapshot artifact is missing its SHA-256 digest")
            result[path] = item
        return result

    old, new = indexed(before), indexed(after)
    items = []
    for path in sorted(set(old) | set(new)):
        prior, current = old.get(path), new.get(path)
        if prior is None:
            kind, disposition = "added", "new"
        elif current is None:
            kind, disposition = "deleted", "unresolved-retain"
        elif prior["sha256"] == current["sha256"]:
            kind, disposition = "unchanged", "retained"
        else:
            kind, disposition = "modified", "superseded-recoverably"
        items.append({
            "path": path, "change_kind": kind, "before": prior, "after": current,
            "disposition": disposition,
        })
    manifest = {
        "schema": "merlin-change-manifest/1",
        "operation_id": operation_id,
        "actor": actor,
        "reason": reason,
        "before_manifest_sha256": hashlib.sha256(_canonical(before)).hexdigest(),
        "after_manifest_sha256": hashlib.sha256(_canonical(after)).hexdigest(),
        "items": items,
    }
    manifest["manifest_sha256"] = hashlib.sha256(_canonical(manifest)).hexdigest()
    return manifest


def validate_change_manifest(
    manifest: dict[str, Any], *,
    approval_validator=None,
) -> None:
    """Fail closed on missing dispositions, unapproved deletion, or hash mismatch."""
    if manifest.get("schema") != "merlin-change-manifest/1":
        raise ValueError("unsupported change manifest schema")
    claimed = manifest.get("manifest_sha256")
    unsigned = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    if hashlib.sha256(_canonical(unsigned)).hexdigest() != claimed:
        raise ValueError("change manifest digest mismatch")
    seen = set()
    for item in manifest.get("items", []):
        path = item.get("path")
        if not path or path in seen or not item.get("disposition"):
            raise ValueError("change manifest has missing or duplicate path disposition")
        seen.add(path)
        if item.get("change_kind") == "deleted":
            if (item["disposition"] != "approved-retirement"
                    or not item.get("approval_ref")
                    or not callable(approval_validator)
                    or approval_validator(item["approval_ref"], item) is not True):
                raise ValueError(f"deletion lacks independently validated approval; preserve artifact: {path}")
        if item.get("change_kind") == "modified" and item["disposition"] not in {
            "superseded-recoverably", "approved-retirement"
        }:
            raise ValueError(f"modified artifact lacks recoverable predecessor: {path}")
        if item.get("change_kind") == "modified" and item["disposition"] == "superseded-recoverably":
            if not item.get("before") or not item.get("after"):
                raise ValueError(f"modified artifact lacks both predecessor and successor: {path}")
