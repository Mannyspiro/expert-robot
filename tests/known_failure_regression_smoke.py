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
assert "formal-dependency-drift" in ids
assert len(ids) >= 11
allowed_guards = {
    "tests/known_failure_regression_smoke.py",
    "tests/formal_dependency_lock_smoke.py",
    "tests/route_planner_smoke.cpp",
}
for item in classes:
    assert item["prevention"]
    assert item["guard"] in allowed_guards
    assert (ROOT / item["guard"]).exists()

# Cross-repository guards use the registry as the single mutable pin source.
# This smoke validates the complete path::test reference and pin structure;
# it deliberately does not duplicate the upstream commit/run/digest literals.
expected_cace_guards = {
    "artifact-ref-key-symlink-parent":
        "test_artifact_ref_key_initializer_rejects_symlinked_parent",
    "artifact-ref-key-unsafe-parent-permissions":
        "test_artifact_ref_key_initializer_rejects_unsafe_directory_and_hardlinks",
    "artifact-ref-key-hardlink-substitution":
        "test_artifact_ref_key_initializer_rejects_unsafe_directory_and_hardlinks",
    "artifact-ref-key-concurrent-initialization":
        "test_artifact_ref_key_initializer_serializes_concurrent_creation",
    "artifact-ref-key-interrupted-publication":
        "test_artifact_ref_key_initializer_cleans_partial_temp_on_write_failure",
}
cace_guard_items = {
    item["id"]: item for item in classes
    if item["id"].startswith("artifact-ref-key-")
}
assert set(cace_guard_items) == set(expected_cace_guards)
assert "cross-repo-test-reference-path-mismatch" in ids
assert "cross-repo-evidence-pin-duplication" in ids
assert "backup-verifier-trigger-name-spoof" in ids

for item in classes:
    external_test = item.get("external_regression_test")
    if external_test is not None:
        assert isinstance(external_test, dict)
        assert set(external_test) == {"repository", "path", "test"}
        assert isinstance(external_test["repository"], str) and external_test["repository"]
        assert isinstance(external_test["path"], str) and external_test["path"]
        assert external_test["test"].startswith(external_test["path"] + "::")
external_pin = None
for class_id, test_name in expected_cace_guards.items():
    external = cace_guard_items[class_id].get("external_guard")
    assert isinstance(external, dict)
    assert set(external) == {
        "repository", "pull_request", "path", "exact_head",
        "workflow_run_id", "artifact_sha256", "test",
    }
    assert external["repository"] == "morganaspim/Cace-app"
    assert type(external["pull_request"]) is int and external["pull_request"] == 103
    assert external["path"] == "tests/test_merlin_artifact_ref.py"
    head = external["exact_head"]
    assert isinstance(head, str) and len(head) == 40
    assert all(char in "0123456789abcdef" for char in head)
    run_id = external["workflow_run_id"]
    assert type(run_id) is int and run_id > 0
    digest = external["artifact_sha256"]
    assert isinstance(digest, str) and len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
    assert external["test"] == external["path"] + "::" + test_name
    pin = (
        external["repository"], external["pull_request"], external["path"],
        head, run_id, digest,
    )
    if external_pin is None:
        external_pin = pin
    else:
        assert pin == external_pin

# Optional fully qualified local regression-test links must resolve to a
# real test method, not merely an existing file.
for item in classes:
    regression_test = item.get("regression_test")
    if regression_test is not None:
        assert isinstance(regression_test, str) and regression_test.count("::") == 1
        test_path, qualified_name = regression_test.split("::", 1)
        test_file = ROOT / test_path
        assert test_file.is_file()
        test_method = qualified_name.rsplit(".", 1)[-1]
        assert f"def {test_method}(" in test_file.read_text(encoding="utf-8")

backup_fixture = next(
    item for item in classes
    if item["id"] == "backup-tamper-fixture-precondition-masking"
)
external_regression = backup_fixture.get("external_regression_test")
assert isinstance(external_regression, dict)
assert set(external_regression) == {"repository", "path", "test"}
assert external_regression["repository"] == "Mannyspiro/expert-robot"
assert external_regression["path"] == "tests/test_qualification_evidence_dag.py"
assert external_regression["test"] == (
    external_regression["path"] + "::"
    "QualificationEvidenceDagSnapshotHistoryTests."
    "test_backup_verification_rejects_tampered_snapshot_rows"
)

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
bridge_docs = (
    ROOT / "docs" / "AI_RUNNER_AND_BRIDGE_OPERATIONS.md"
).read_text(encoding="utf-8")
bridge_summary = (
    ROOT / "docs" / "cace-bidirectional-bridge.md"
).read_text(encoding="utf-8")

# Expert Robot is the Avrea dispatcher and result consumer. The CACE OCI
# workflow remains canonical in CACE-app; do not duplicate it in this repo.
assert '"schema_version": 2' in external
assert '"requested_lane": "cace-oci-aarch64"' in external
assert "CACE's canonical workflow" in external
assert "permissions:\n  contents: write" in external
assert "persist-credentials: true" in external
assert "name: Await external free-runner evidence" in external
assert "name: Upload external runner evidence" in external
assert 'result.get("schema_version") == 3' in external
assert 'result.get("request_id") == expected_request' in external
assert 'result.get("expert_robot_commit") == expected_source' in external
assert 'result.get("cace_repository") == "morganaspim/Cace-app"' in external
assert 'result.get("cace_workflow_id") == 367390621' in external
assert 'result.get("status") in ("pass", "fail")' in external
assert 'result.get("authority") == "qualification-only"' in external
assert 'result.get("promotion_authority") is False' in external
assert 'result.get("result_log_sha256")' in external
assert 'result.get("result_log_size_bytes")' in external
assert "permissions:\n  contents: write" in external
assert "persist-credentials: true" in external
assert "cmake --build" not in external

# CACE owns the self-hosted ARM64 qualification and the separate publisher.
assert "self-hosted, cace, oci, aarch64" in bridge_docs
assert "publish-result" in bridge_docs
assert "unsafe archive members" in bridge_docs
assert "EXPERT_ROBOT_SSH_PRIVATE_KEY" in bridge_docs
assert "promotion_authority=false" in bridge_docs
assert "SSH proves repository transport access only" in bridge_summary

proof_search = json.loads(
    (ROOT / "config" / "proof_search.json").read_text(encoding="utf-8")
)
proof_search_text = "\n".join(proof_search["strategies"])
for forbidden in (
    "validation-geometry-dot-zero-right",
    "validation-geometry-cross-self",
    "holdout-geometry-orthogonal-symm",
    "holdout-geometry-distance-symm",
    "holdout-geometry-distance-nonnegative",
    "holdout-geometry-zero-orthogonal-left",
    "holdout-geometry-sphere-radius",
    "MathAI.Geometry.dot_zero_right",
    "MathAI.Geometry.cross_self",
    "MathAI.Geometry.orthogonal_symm",
    "MathAI.Geometry.squaredDistance_symm",
    "MathAI.Geometry.squaredDistance_nonnegative",
    "MathAI.Geometry.zero_orthogonal_left",
    "MathAI.Geometry.squaredDistance_eq_radius_of_pointOnSphere",
):
    assert forbidden not in proof_search_text

route_planner = (
    ROOT / "cpp" / "src" / "research" / "route_planner.cpp"
).read_text(encoding="utf-8")
route_planner_test = (
    ROOT / "tests" / "route_planner_smoke.cpp"
).read_text(encoding="utf-8")
assert "directionally_traversable" in route_planner
assert 'edge.relation == "USES"' in route_planner
assert 'edge.relation == "REQUIRES"' in route_planner
assert "edge.source == current" in route_planner
assert "MathAI.Dependent" in route_planner_test
assert "reverse_dependency == routes.end()" in route_planner_test

print("known failure regression guardrails: PASS")
