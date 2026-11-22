#!/usr/bin/env bash
# Reproduce Merlin CI against an existing, exact-revision checkout.
# No source downloads, credentials, deployment, or release promotion.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "ERROR: complete Git checkout required" >&2
  exit 2
fi
SHA="$(git rev-parse HEAD)"
if [ -n "${MERLIN_EXPECTED_SHA:-}" ] && [ "$SHA" != "$MERLIN_EXPECTED_SHA" ]; then
  echo "ERROR: wrong revision: $SHA" >&2
  exit 3
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: checkout has uncommitted changes" >&2
  exit 4
fi
OUT="${MERLIN_CI_EVIDENCE_DIR:-$ROOT/build/merlin-ci-evidence}"
mkdir -p "$OUT"
# Preserve failure evidence too: a failed step must not erase its diagnostics.
finalize_evidence() {
  local result=$?
  trap - EXIT
  printf "overall_exit=%s\n" "$result" > "$OUT/result.txt"
  (cd "$OUT" && sha256sum ./*.log environment.txt exit-codes.txt result.txt > SHA256SUMS) 2>/dev/null || true
  exit "$result"
}
trap finalize_evidence EXIT
{
  echo "source_sha=$SHA"
  echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "host=$(uname -a)"
  echo "python=$(python3 --version 2>&1)"
  echo "cmake=$(cmake --version | head -n 1)"
  echo "ninja=$(ninja --version)"
} > "$OUT/environment.txt"
run_step() {
  local name="$1"
  shift
  set +e
  "$@" > "$OUT/$name.log" 2>&1
  local code=$?
  set -e
  printf '%s %s\n' "$name" "$code" >> "$OUT/exit-codes.txt"
  if [ "$code" -ne 0 ]; then
    echo "FAIL $name ($code): $OUT/$name.log" >&2
    exit "$code"
  fi
}
: > "$OUT/exit-codes.txt"
run_step shell-preflight bash -c 'for script in scripts/*.sh; do bash -n "$script" || exit; done'
run_step cmake-configure cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
run_step cmake-build cmake --build build --parallel 2
run_step ctest ctest --test-dir build --parallel 2 --output-on-failure
run_step merlin-loop-tests python3 -m unittest discover -s tests -p 'test_merlin_loop_*.py' -v
run_step merlin-dependency-tests python3 -m unittest discover -s tests -p 'test_merlin_dependency_math.py' -v
run_step merlin-reframing-tests python3 -m unittest discover -s tests -p 'test_merlin_tool_reframing.py' -v
run_step merlin-release-tests python3 -m unittest discover -s tests -p 'test_merlin_release_gate.py' -v
run_step compute-policy python3 tests/compute_policy_smoke.py
run_step known-failure python3 tests/known_failure_regression_smoke.py
run_step benchmark-baseline python3 tests/benchmark_baseline_smoke.py
run_step progression-benchmark python3 tests/progression_benchmark_smoke.py
run_step progression-baseline-integrity python3 tests/progression_baseline_integrity_smoke.py
run_step progression-freezer python3 tests/progression_freezer_smoke.py
run_step formal-dependency python3 tests/formal_dependency_lock_smoke.py
run_step cace-bridge python3 tests/cace_return_bridge_smoke.py
run_step collar-policy python3 tests/collar_policy_smoke.py
run_step collar-runtime python3 tests/collar_runtime_contract_smoke.py
run_step collar-vault bash tests/collar_vault_smoke.sh
run_step runtime-smoke python3 tests/smoke.py ./build/expert_robot_runtime
run_step research-contract python3 tests/research_cli_contract_smoke.py
echo "PASS: $SHA; evidence: $OUT"
