#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${ER_PREFLIGHT_MODE:-cheap}"
BUILD_DIR="${ER_BUILD_DIR:-build/preflight}"
BASE_REF="${ER_BASE_REF:-origin/main}"

say() {
  printf '[preflight] %s\n' "$*"
}

cpu="$(nproc 2>/dev/null || getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)"
mem_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
mem_mb="$((mem_kb / 1024))"

if [ -n "${ER_PREFLIGHT_JOBS:-}" ]; then
  jobs="$ER_PREFLIGHT_JOBS"
elif [ "$mem_mb" -gt 0 ] && [ "$mem_mb" -le 3072 ]; then
  jobs=1
elif [ "$cpu" -gt 4 ]; then
  jobs=4
else
  jobs="$cpu"
fi

if ! [[ "$jobs" =~ ^[1-9][0-9]*$ ]]; then
  say "invalid ER_PREFLIGHT_JOBS=$jobs"
  exit 2
fi

say "mode=$MODE cpu=$cpu memory_mb=$mem_mb build_jobs=$jobs"
say "authority: preflight may reject a candidate; a pass never promotes it"

python3 tests/compute_policy_smoke.py
python3 tests/known_failure_regression_smoke.py
python3 tests/formal_dependency_lock_smoke.py
python3 tests/cace_return_bridge_smoke.py

cmake -S . -B "$BUILD_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release

case "$MODE" in
  cheap)
    targets=(
      route_memory_smoke
      strategy_engine_complete_smoke
      research_benchmark_executor_smoke
      expert_robot_runtime
    )
    test_regex='route_memory_smoke|strategy_engine_complete_smoke|research_benchmark_executor_smoke'
    ;;
  targeted)
    targets=(
      route_memory_smoke
      strategy_planner_smoke
      strategy_engine_complete_smoke
      math_benchmark_smoke
      research_benchmark_executor_smoke
      expert_robot_runtime
    )
    test_regex='route_memory_smoke|strategy_planner_smoke|strategy_engine_complete_smoke|math_benchmark_smoke|research_benchmark_executor_smoke'
    ;;
  full)
    targets=(expert_robot_runtime)
    test_regex='.*'
    ;;
  *)
    say "unknown mode '$MODE' (expected cheap, targeted, or full)"
    exit 2
    ;;
esac

if [ "$MODE" = "full" ]; then
  say "building full C++ tree"
  cmake --build "$BUILD_DIR" --parallel "$jobs"
else
  say "building focused targets: ${targets[*]}"
  cmake --build "$BUILD_DIR" --parallel "$jobs" --target "${targets[@]}"
fi

say "running C++ tests sequentially on low-memory workers"
ctest --test-dir "$BUILD_DIR" -R "$test_regex" --parallel 1 --output-on-failure

if [ -x "$BUILD_DIR/expert_robot_runtime" ]; then
  say "running independent runtime smoke"
  python3 tests/smoke.py "$BUILD_DIR/expert_robot_runtime"
fi

changed_lean=()
if [ -d formal ] && command -v lake >/dev/null 2>&1; then
  if git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
    while IFS= read -r file; do
      [ -n "$file" ] && changed_lean+=("$file")
    done < <(git diff --name-only "$BASE_REF"...HEAD -- 'formal/*.lean' 'formal/**/*.lean')
  elif git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    while IFS= read -r file; do
      [ -n "$file" ] && changed_lean+=("$file")
    done < <(git diff --name-only HEAD~1 HEAD -- 'formal/*.lean' 'formal/**/*.lean')
  fi
fi

if [ "${#changed_lean[@]}" -gt 0 ]; then
  say "checking changed Lean files sequentially"
  for file in "${changed_lean[@]}"; do
    relative="${file#formal/}"
    say "Lean check: $relative"
    (
      cd formal
      LEAN_NUM_THREADS=1 lake env lean "$relative"
    )
  done
else
  say "no changed Lean files detected; skipping Lean compile in cheap preflight"
fi

mkdir -p "$BUILD_DIR"
python3 - "$BUILD_DIR/preflight-summary.json" "$MODE" "$cpu" "$mem_mb" "$jobs" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "mode": sys.argv[2],
    "detected_cpu": int(sys.argv[3]),
    "detected_memory_mb": int(sys.argv[4]),
    "build_jobs": int(sys.argv[5]),
    "passed": True,
    "qualification_authority": False,
    "promotion_authority": False,
}
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"[preflight] evidence written to {path}")
PY

say "PASS: cheap evidence is suitable for escalation, not promotion"
