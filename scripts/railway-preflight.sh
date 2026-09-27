#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bootstrap=false
for arg in "$@"; do
  case "$arg" in
    --bootstrap)
      bootstrap=true
      ;;
    *)
      printf '[railway-preflight] unknown argument: %s\n' "$arg" >&2
      exit 2
      ;;
  esac
done

if "$bootstrap"; then
  bash "$ROOT/scripts/bootstrap-railway-worker.sh"
fi

export PATH="$HOME/.elan/bin:$PATH"

# The anonymous/free Railway VM is 2 vCPU / 2 GB today. Keep compile and test
# concurrency deliberately conservative unless an operator overrides it.
: "${ER_PREFLIGHT_JOBS:=1}"
: "${ER_PREFLIGHT_MODE:=cheap}"
export ER_PREFLIGHT_JOBS ER_PREFLIGHT_MODE

exec bash "$ROOT/scripts/preflight.sh"
