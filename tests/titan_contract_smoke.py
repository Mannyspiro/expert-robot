#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate_titan_record.py"

def run(kind, record):
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "record.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        return subprocess.run([sys.executable, str(VALIDATOR), kind, str(path)], text=True, capture_output=True)

candidate = {
    "schema_version": 1,
    "candidate_id": "titan:baseline-mlkem",
    "title": "ML-KEM baseline reference profile",
    "status": "formalized",
    "objective": "Establish a reproducible standardized post-quantum KEM baseline.",
    "threat_model": ["quantum", "active_network"],
    "primitive_families": ["lattice_kem"],
    "mathematical_lenses": ["lattice_geometry", "information_theory"],
    "assumptions": ["Use the standardized ML-KEM security model and parameter set."],
    "claims": ["This record identifies a baseline, not a new security proof."],
    "limitations": ["Implementation validation and external review remain outstanding."],
    "provenance": {"repository": "Mannyspiro/expert-robot", "commit_sha": "a" * 40, "created_at": "2026-11-05T12:00:00Z"},
    "production_eligible": False
}
assert run("candidate", candidate).returncode == 0
bad_candidate = dict(candidate, production_eligible=True)
assert run("candidate", bad_candidate).returncode != 0
bad_candidate = dict(candidate, candidate_id="../escape")
assert run("candidate", bad_candidate).returncode != 0
bad_candidate = dict(candidate, threat_model=["quantum", "quantum"])
assert run("candidate", bad_candidate).returncode != 0

experiment = {
    "schema_version": 1,
    "experiment_id": "titan-run:baseline-smoke-001",
    "candidate_id": "titan:baseline-mlkem",
    "source": {"repository": "Mannyspiro/expert-robot", "commit_sha": "b" * 40, "dirty": False},
    "runner": {"identity": "local-smoke", "toolchain": "python-stdlib"},
    "execution": {"command": ["python3", "tests/titan_contract_smoke.py"], "started_at": "2026-11-05T12:00:00Z", "finished_at": "2026-11-05T12:00:01Z", "exit_code": 0, "timeout_seconds": 30},
    "inputs": [{"name": "fixture", "sha256": "c" * 64, "media_type": "application/json"}],
    "outputs": [{"name": "result", "sha256": "d" * 64, "media_type": "application/json"}],
    "result": {"status": "pass", "summary": "Synthetic contract fixture only.", "test_vector_count": 0},
    "authority": "qualification-only",
    "promotion_authority": False,
    "secret_material_included": False
}
assert run("experiment", experiment).returncode == 0
bad_experiment = dict(experiment, promotion_authority=True)
assert run("experiment", bad_experiment).returncode != 0
bad_experiment = dict(experiment, source={"repository": "repo", "commit_sha": "not-a-sha", "dirty": False})
assert run("experiment", bad_experiment).returncode != 0
bad_experiment = dict(experiment, secret_material_included=True)
assert run("experiment", bad_experiment).returncode != 0

print("Titan candidate/experiment contract smoke: PASS")
