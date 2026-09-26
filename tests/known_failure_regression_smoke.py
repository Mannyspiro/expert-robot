#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

registry = json.loads(
    (ROOT / "config" / "known_failure_classes.json").read_text(encoding="utf-8")
)
assert registry["schema_version"] == 1
classes = registry["classes"]
ids = [item["id"] for item in classes]
assert len(ids) == len(set(ids))
assert len(ids) >= 7
allowed_guards = {
    "tests/known_failure_regression_smoke.py",
    "tests/formal_dependency_lock_smoke.py",
}
for item in classes:
    assert item["prevention"]
    assert item["guard"] in allowed_guards
    assert (ROOT / item["guard"]).exists()

cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
assert "-Werror=missing-field-initializers" in cmake
assert "-Werror=range-loop-construct" in cmake

memory = (ROOT / "cpp" / "src" / "imagination" / "memory.cpp").read_text(
    encoding="utf-8"
)
assert ".skill_id = {}" in memory

benchmark = (ROOT / "cpp" / "src" / "eval" / "math_benchmark.cpp").read_text(
    encoding="utf-8"
)
assert "for (const std::string& domain :" in benchmark

route_memory = (ROOT / "cpp" / "src" / "research" / "route_memory.cpp").read_text(
    encoding="utf-8"
)
assert route_memory.count(".signature = {}") >= 3

exact = (ROOT / "formal" / "MathAI" / "Geometry" / "Exact.lean").read_text(
    encoding="utf-8"
)
assert "@[ext] theorem Vec3.ext_coords" in exact
assert "@[ext] theorem Point3.ext_coords" in exact

vector = (
    ROOT / "formal" / "MathAI" / "Geometry" / "VectorDerived.lean"
).read_text(encoding="utf-8")
assert "sq_nonneg a.x" in vector
assert "sq_nonneg a.y" in vector
assert "sq_nonneg a.z" in vector
assert "nlinarith" in vector

railway = (
    ROOT / ".github" / "workflows" / "railway-free-preflight.yml"
).read_text(encoding="utf-8")
assert "human_claim_url" in railway
assert "ssh \\\n            -A" not in railway
assert "Discover runner repository with deploy key" in railway

secure = (
    ROOT / ".github" / "workflows" / "secure-railway-ssh-check.yml"
).read_text(encoding="utf-8")
assert 'awk \'!/"human_claim_url":/\'' in secure

external = (
    ROOT / ".github" / "workflows" / "external-free-runner-bridge.yml"
).read_text(encoding="utf-8")
assert '"qualification_lane": "formal-static-arm64"' in external
assert '"cxx_required": False' in external
assert '"self_hosted_contents_write": False' in external
assert "runs-on: [self-hosted, cace, oci, aarch64]" in external
assert "persist-credentials: false" in external
assert "publish-result:" in external
assert "name: Upload read-only runner evidence" in external
assert "contents: read" in external
assert "contents: write" in external
assert "unsafe archive path" in external
assert "unsafe archive member type" in external
assert '("run_cmd", re.compile' in external
assert "cmake --build" not in external

print("known failure regression guardrails: PASS")
