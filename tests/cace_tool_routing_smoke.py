#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLANNER = ROOT / "scripts" / "plan_cace_tool_requests.py"
VALIDATOR = ROOT / "scripts" / "validate_cace_tool_result.py"
POLICY = ROOT / "config" / "cace_tool_broker.json"

SOURCE = "a" * 40
INPUT = "b" * 64
PIN = "0e7aa229d3bb57174e281b883ee8af5445f15f75"
CAPABILITY = "cace.external.expert_robot_formal_static"


def plan(*paths):
    run = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            str(POLICY),
            SOURCE,
            "feat/routing-smoke",
            INPUT,
            *paths,
        ],
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def canonical_sha(payload):
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def validator_accepts(request):
    result = {
        "schema_version": 1,
        "request_id": request["request_id"],
        "source_repository": request["source_repository"],
        "source_commit": request["source_commit"],
        "cace_repository": request["cace_repository"],
        "cace_commit": request["cace_commit"],
        "capability_id": request["capability_id"],
        "status": "pass",
        "cace_run_id": "routing-smoke-run",
        "authority": "qualification-only",
        "promotion_authority": False,
        "monetary_cost": "free",
        "compute": {
            "wall_seconds": min(5, request["budget"]["wall_seconds"]),
            "lean_checks": min(1, request["budget"]["lean_checks"]),
        },
        "evidence_sha256": "c" * 64,
    }
    result["result_sha256"] = canonical_sha(result)

    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        req = tmp / "request.json"
        res = tmp / "result.json"
        req.write_text(json.dumps(request), encoding="utf-8")
        res.write_text(json.dumps(result), encoding="utf-8")
        run = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR),
                str(POLICY),
                str(req),
                str(res),
            ],
            text=True,
            capture_output=True,
        )
        assert run.returncode == 0, run.stderr


# Expert Robot formal source uses the reviewed source-bundle bridge, never a
# native Cace-app formal workflow.
single = plan("formal/MathAI/Geometry/Exact.lean")
assert single["cace_commit"] == PIN
assert single["requires_avrea"] is False
assert len(single["cace_requests"]) == 1
request = single["cace_requests"][0]
assert request["capability_id"] == CAPABILITY
assert request["executor_kind"] == "expert-robot-source-bundle"
assert request["workflow_repository"] == "Mannyspiro/expert-robot"
assert request["workflow"] == ".github/workflows/external-free-runner-bridge.yml"
assert request["budget"] == {"wall_seconds": 1200, "lean_checks": 40}
assert request["promotion_authority"] is False
assert request["monetary_cost"] == "free"
validator_accepts(request)

# Multiple Expert Robot Lean paths use the same source-bundle qualification
# contract because the external lane qualifies the submitted Expert Robot
# source tree, not Cace-app's CACEFormal targets.
batch = plan(
    "formal/MathAI/Geometry/Exact.lean",
    "formal/MathAI/Geometry/VectorDerived.lean",
)
assert len(batch["cace_requests"]) == 1
assert batch["cace_requests"][0]["capability_id"] == CAPABILITY
assert batch["cace_requests"][0]["changed_paths"] == [
    "formal/MathAI/Geometry/Exact.lean",
    "formal/MathAI/Geometry/VectorDerived.lean",
]
validator_accepts(batch["cace_requests"][0])

# CACE-native Python regression operates on Cace-app source. It is therefore
# not callable for Expert Robot Python changes.
python_plan = plan("python/orchestrator.py")
assert python_plan["cace_requests"] == []
assert python_plan["requires_avrea"] is False
assert any(
    "not routed to CACE-native Python regression" in reason
    for reason in python_plan["reasons"]
)

# Lean build/dependency infrastructure is never executed in the async CACE
# source-bundle lane.
formal_infra = plan("formal/lakefile.toml")
assert formal_infra["cace_requests"] == []
assert formal_infra["requires_avrea"] is True
assert formal_infra["avrea_paths"] == ["formal/lakefile.toml"]
assert any(
    "Lean build/dependency infrastructure changes require repository qualification"
    in reason
    for reason in formal_infra["reasons"]
)

# C++/model/runtime work still requires Avrea.
cpp_plan = plan("cpp/src/runtime.cpp", "CMakeLists.txt")
assert cpp_plan["cace_requests"] == []
assert cpp_plan["requires_avrea"] is True
assert sorted(cpp_plan["avrea_paths"]) == [
    "CMakeLists.txt",
    "cpp/src/runtime.cpp",
]

# Mixed formal/C++ gets the legitimate formal CACE evidence first while Avrea
# remains required for repository qualification.
mixed = plan("formal/MathAI/Geometry/Exact.lean", "cpp/src/runtime.cpp")
assert mixed["requires_avrea"] is True
assert len(mixed["cace_requests"]) == 1
assert mixed["cace_requests"][0]["capability_id"] == CAPABILITY
validator_accepts(mixed["cace_requests"][0])

# CACE-native collaboration validation is also scoped to Cace-app source.
collab = plan("collaboration/contracts/workspace.json")
assert collab["cace_requests"] == []
assert collab["requires_avrea"] is False
assert any(
    "not routed to CACE-native collaboration validation" in reason
    for reason in collab["reasons"]
)

# Docs-only changes do not consume external verifier compute.
docs = plan("docs/research-engine.md")
assert docs["cace_requests"] == []
assert docs["requires_avrea"] is False
assert docs["repository_ci_required"] is True
assert docs["automatic_dispatch"] is False
assert docs["automatic_promotion"] is False

# Determinism.
again = plan("formal/MathAI/Geometry/Exact.lean")
assert single == again

# Path traversal is rejected before routing.
run = subprocess.run(
    [
        sys.executable,
        str(PLANNER),
        str(POLICY),
        SOURCE,
        "feat/routing-smoke",
        INPUT,
        "../formal/escape.lean",
    ],
    text=True,
    capture_output=True,
)
assert run.returncode != 0
assert "unsafe changed path" in (run.stderr + run.stdout)

# Invalid source identity is rejected before capability selection.
run = subprocess.run(
    [
        sys.executable,
        str(PLANNER),
        str(POLICY),
        "not-a-commit",
        "feat/routing-smoke",
        INPUT,
        "formal/MathAI/Geometry/Exact.lean",
    ],
    text=True,
    capture_output=True,
)
assert run.returncode != 0
assert "source commit" in (run.stderr + run.stdout)

print("CACE tool routing guardrails: PASS")
