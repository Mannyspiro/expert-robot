"""Versioned persistence and deterministic diffs for Merlin engineering projects."""
from __future__ import annotations

from contextlib import closing

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from merlin.engineering_ir import EngineeringProject, Net, Part, Pin, validate_project

SCHEMA_VERSION = 1

def project_to_dict(project: EngineeringProject) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": project.name,
        "units": project.units,
        "metadata": dict(sorted(project.metadata.items())),
        "parts": [
            {
                "ref": part.ref, "name": part.name,
                "pins": [asdict(pin) for pin in sorted(part.pins, key=lambda p: p.number)],
                "size_mm": list(part.size_mm),
                "position_mm": list(part.position_mm),
                "model": part.model,
            }
            for part in sorted(project.parts, key=lambda p: p.ref)
        ],
        "nets": [
            {
                "name": net.name, "endpoints": sorted(net.endpoints),
                "nominal_voltage_v": net.nominal_voltage_v,
                "max_current_a": net.max_current_a, "net_class": net.net_class,
            }
            for net in sorted(project.nets, key=lambda n: n.name)
        ],
    }

def canonical_json(project: EngineeringProject) -> str:
    return json.dumps(project_to_dict(project), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)

def project_hash(project: EngineeringProject) -> str:
    return hashlib.sha256(canonical_json(project).encode("utf-8")).hexdigest()

def project_from_dict(data: dict[str, Any]) -> EngineeringProject:
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported engineering project schema version")
    try:
        parts = tuple(Part(
            ref=item["ref"], name=item["name"],
            pins=tuple(Pin(**pin) for pin in item.get("pins", [])),
            size_mm=tuple(item.get("size_mm", (10.0, 10.0, 3.0))),
            position_mm=tuple(item.get("position_mm", (0.0, 0.0, 0.0))),
            model=item.get("model", "box"),
        ) for item in data["parts"])
        nets = tuple(Net(
            name=item["name"], endpoints=tuple(item["endpoints"]),
            nominal_voltage_v=item.get("nominal_voltage_v"),
            max_current_a=item.get("max_current_a"),
            net_class=item.get("net_class", "signal"),
        ) for item in data["nets"])
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()
        ):
            raise ValueError("metadata must be a string-to-string object")
        project = EngineeringProject(
            name=data["name"], units=data["units"], parts=parts, nets=nets, metadata=metadata
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("malformed engineering project document") from exc
    issues = validate_project(project)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise ValueError("project document failed validation: " + "; ".join(i.code for i in errors))
    return project

def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            path = prefix + "/" + str(key).replace("~", "~0").replace("/", "~1")
            result.update(_flatten(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(_flatten(item, prefix + "/" + str(index)))
    else:
        result[prefix or "/"] = value
    return result

def deterministic_diff(before: EngineeringProject, after: EngineeringProject) -> list[dict[str, Any]]:
    left, right = _flatten(project_to_dict(before)), _flatten(project_to_dict(after))
    changes = []
    for path in sorted(set(left) | set(right)):
        if path not in left:
            changes.append({"path": path, "operation": "add", "after": right[path]})
        elif path not in right:
            changes.append({"path": path, "operation": "remove", "before": left[path]})
        elif left[path] != right[path]:
            changes.append({"path": path, "operation": "replace",
                            "before": left[path], "after": right[path]})
    return changes

class EngineeringProjectStore:
    """Append-only project snapshots with monotonic revisions and hash chaining."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS engineering_projects (
                    project_id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS engineering_revisions (
                    project_id TEXT NOT NULL REFERENCES engineering_projects(project_id),
                    revision INTEGER NOT NULL, schema_version INTEGER NOT NULL,
                    content_json TEXT NOT NULL, content_hash TEXT NOT NULL,
                    parent_hash TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(project_id, revision),
                    UNIQUE(project_id, content_hash)
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database, timeout=15.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def save(self, project_id: str, project: EngineeringProject) -> dict[str, Any]:
        identifier = project_id.strip()
        if not identifier or len(identifier) > 120:
            raise ValueError("project_id must be 1 to 120 characters")
        issues = validate_project(project)
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            raise ValueError("cannot save invalid project: " + "; ".join(i.code for i in errors))
        document = project_to_dict(project)
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self._connect()) as db, db:
            db.execute("INSERT OR IGNORE INTO engineering_projects VALUES (?, ?, ?)",
                       (identifier, project.name, now))
            latest = db.execute(
                "SELECT revision, content_hash FROM engineering_revisions WHERE project_id=? ORDER BY revision DESC LIMIT 1",
                (identifier,),
            ).fetchone()
            if latest and latest["content_hash"] == digest:
                return {"project_id": identifier, "revision": latest["revision"],
                        "content_hash": digest, "parent_hash": latest["content_hash"], "unchanged": True}
            revision = 1 if latest is None else latest["revision"] + 1
            parent_hash = "" if latest is None else latest["content_hash"]
            db.execute("INSERT INTO engineering_revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (identifier, revision, SCHEMA_VERSION, encoded, digest, parent_hash, now))
        return {"project_id": identifier, "revision": revision, "content_hash": digest,
                "parent_hash": parent_hash, "unchanged": False}

    def load(self, project_id: str, revision: int | None = None) -> EngineeringProject:
        with closing(self._connect()) as db, db:
            if revision is None:
                row = db.execute(
                    "SELECT content_json FROM engineering_revisions WHERE project_id=? ORDER BY revision DESC LIMIT 1",
                    (project_id,),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT content_json FROM engineering_revisions WHERE project_id=? AND revision=?",
                    (project_id, revision),
                ).fetchone()
        if row is None:
            raise KeyError((project_id, revision))
        return project_from_dict(json.loads(row["content_json"]))

    def history(self, project_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as db, db:
            rows = db.execute(
                "SELECT revision, content_hash, parent_hash, created_at FROM engineering_revisions WHERE project_id=? ORDER BY revision",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def diff(self, project_id: str, before_revision: int, after_revision: int) -> list[dict[str, Any]]:
        before = self.load(project_id, before_revision)
        after = self.load(project_id, after_revision)
        return deterministic_diff(before, after)

    def verify_history(self, project_id: str) -> bool:
        history = self.history(project_id)
        previous = ""
        for item in history:
            revision = item["revision"]
            project = self.load(project_id, revision)
            digest = project_hash(project)
            if digest != item["content_hash"] or item["parent_hash"] != previous:
                return False
            previous = digest
        return True
