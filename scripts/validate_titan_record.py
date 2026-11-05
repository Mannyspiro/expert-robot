#!/usr/bin/env python3
"""Dependency-free structural validator for Titan candidate and experiment records."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CANDIDATE_ID = re.compile(r"^titan:[a-z0-9][a-z0-9._-]{2,95}$")
EXPERIMENT_ID = re.compile(r"^titan-run:[A-Za-z0-9._-]{3,120}$")

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def timestamp(value: object, field: str) -> None:
    require(isinstance(value, str), f"{field} must be an ISO-8601 string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from exc

def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path}: root must be an object")
    return value

def validate_candidate(v: dict) -> None:
    required = {"schema_version", "candidate_id", "title", "status", "objective", "threat_model", "primitive_families", "mathematical_lenses", "assumptions", "claims", "limitations", "provenance"}
    require(required <= v.keys(), f"candidate missing fields: {sorted(required - v.keys())}")
    require(v["schema_version"] == 1, "unsupported candidate schema_version")
    require(bool(CANDIDATE_ID.fullmatch(str(v["candidate_id"]))), "invalid candidate_id")
    require(isinstance(v["title"], str) and 3 <= len(v["title"]) <= 180, "invalid title")
    require(v["status"] in {"idea", "formalized", "experimental", "review_required", "rejected", "qualified"}, "invalid candidate status")
    for field in ("threat_model", "primitive_families", "mathematical_lenses", "assumptions", "claims", "limitations"):
        require(isinstance(v[field], list), f"{field} must be an array")
    for field in ("threat_model", "primitive_families", "mathematical_lenses", "assumptions", "limitations"):
        require(len(v[field]) > 0, f"{field} must not be empty")
    require(len(v["threat_model"]) == len(set(v["threat_model"])), "duplicate threat_model item")
    p = v["provenance"]
    require(isinstance(p, dict), "provenance must be an object")
    require({"repository", "commit_sha", "created_at"} <= p.keys(), "provenance missing required fields")
    require(bool(HEX40.fullmatch(str(p["commit_sha"]))), "invalid provenance commit_sha")
    timestamp(p["created_at"], "provenance.created_at")
    require(v.get("production_eligible", False) is False, "Titan research candidates cannot self-declare production eligibility")

def validate_experiment(v: dict) -> None:
    required = {"schema_version", "experiment_id", "candidate_id", "source", "runner", "execution", "inputs", "outputs", "result", "authority"}
    require(required <= v.keys(), f"experiment missing fields: {sorted(required - v.keys())}")
    require(v["schema_version"] == 1, "unsupported experiment schema_version")
    require(bool(EXPERIMENT_ID.fullmatch(str(v["experiment_id"]))), "invalid experiment_id")
    require(bool(CANDIDATE_ID.fullmatch(str(v["candidate_id"]))), "invalid candidate_id")
    src = v["source"]
    require(isinstance(src, dict) and {"repository", "commit_sha", "dirty"} <= src.keys(), "invalid source binding")
    require(bool(HEX40.fullmatch(str(src["commit_sha"]))), "invalid source commit_sha")
    require(isinstance(src["dirty"], bool), "source.dirty must be boolean")
    runner = v["runner"]
    require(isinstance(runner, dict) and all(isinstance(runner.get(k), str) and runner[k] for k in ("identity", "toolchain")), "runner identity and toolchain required")
    ex = v["execution"]
    require(isinstance(ex, dict) and {"command", "started_at", "finished_at", "exit_code"} <= ex.keys(), "execution binding incomplete")
    require(isinstance(ex["command"], list) and len(ex["command"]) > 0, "execution.command must be a non-empty array")
    timestamp(ex["started_at"], "execution.started_at")
    timestamp(ex["finished_at"], "execution.finished_at")
    require(isinstance(ex["exit_code"], int) and not isinstance(ex["exit_code"], bool), "execution.exit_code must be integer")
    for field in ("inputs", "outputs"):
        require(isinstance(v[field], list), f"{field} must be an array")
        for item in v[field]:
            require(isinstance(item, dict) and {"name", "sha256", "media_type"} <= item.keys(), f"invalid {field} artifact")
            require(bool(HEX64.fullmatch(str(item["sha256"]))), f"invalid {field} artifact sha256")
    result = v["result"]
    require(isinstance(result, dict) and result.get("status") in {"pass", "fail", "inconclusive"} and isinstance(result.get("summary"), str), "invalid experiment result")
    require(v["authority"] == "qualification-only", "experiment authority must be qualification-only")
    require(v.get("promotion_authority", False) is False, "experiment cannot grant promotion authority")
    require(v.get("secret_material_included", False) is False, "secret material is forbidden in experiment records")

def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in {"candidate", "experiment"}:
        print("usage: validate_titan_record.py <candidate|experiment> <json-file>", file=sys.stderr)
        return 2
    try:
        record = load(Path(sys.argv[2]))
        (validate_candidate if sys.argv[1] == "candidate" else validate_experiment)(record)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f"TITAN_INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"TITAN_VALID: {sys.argv[1]}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
