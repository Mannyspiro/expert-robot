#!/usr/bin/env bash
set -euo pipefail

REPO="${ER_REPO:-https://github.com/Mannyspiro/expert-robot.git}"
BRANCH="${ER_BRANCH:-feat/reuse-refactored-fishstick}"
CHECKPOINT="${ER_CHECKPOINT:-expert-robot-preflight}"
WORKDIR="${ER_SANDBOX_WORKDIR:-/workspace/expert-robot}"
IDLE_MINUTES="${ER_SANDBOX_IDLE_MINUTES:-5}"

say() {
  printf '[railway-sandbox] %s\n' "$*"
}

require_railway() {
  if ! command -v railway >/dev/null 2>&1; then
    say "Railway CLI is required."
    exit 2
  fi
}

create_base() {
  say "creating sandbox"
  railway sandbox create --idle-timeout-minutes "$IDLE_MINUTES"

  say "cloning $REPO at $BRANCH"
  railway sandbox exec -- bash -lc "
    set -euo pipefail
    rm -rf '$WORKDIR'
    git clone '$REPO' '$WORKDIR'
    cd '$WORKDIR'
    git checkout '$BRANCH'
    bash ./scripts/bootstrap-railway-worker.sh
  "

  say "capturing checkpoint $CHECKPOINT"
  railway sandbox checkpoint create "$CHECKPOINT"

  say "base checkpoint ready; the source sandbox remains active"
  say "destroy it with: railway sandbox destroy"
}

verify_from_checkpoint() {
  say "creating isolated sandbox from checkpoint $CHECKPOINT"
  railway sandbox create     --checkpoint "$CHECKPOINT"     --idle-timeout-minutes "$IDLE_MINUTES"

  set +e
  railway sandbox exec -- bash -lc "
    set -euo pipefail
    cd '$WORKDIR'
    git fetch origin '$BRANCH'
    git checkout '$BRANCH'
    git reset --hard 'origin/$BRANCH'
    ER_PREFLIGHT_JOBS=1 ER_PREFLIGHT_MODE=cheap       bash ./scripts/railway-preflight.sh
  "
  rc=$?
  set -e

  if [ "$rc" -eq 0 ]; then
    say "preflight PASS; destroying disposable sandbox"
    railway sandbox destroy
    return 0
  fi

  say "preflight FAILED with exit code $rc"
  say "sandbox intentionally kept alive for debugging"
  say "connect with: railway sandbox ssh"
  return "$rc"
}

case "${1:-}" in
  prepare)
    require_railway
    create_base
    ;;
  verify)
    require_railway
    verify_from_checkpoint
    ;;
  shell)
    require_railway
    railway sandbox ssh
    ;;
  destroy)
    require_railway
    railway sandbox destroy
    ;;
  *)
    cat <<EOF
Usage: bash scripts/railway-sandbox-lane.sh <prepare|verify|shell|destroy>

Environment overrides:
  ER_REPO=$REPO
  ER_BRANCH=$BRANCH
  ER_CHECKPOINT=$CHECKPOINT
  ER_SANDBOX_WORKDIR=$WORKDIR
  ER_SANDBOX_IDLE_MINUTES=$IDLE_MINUTES

prepare  Create a sandbox, clone/bootstrap the repo, and capture the checkpoint.
verify   Boot an isolated checkpoint copy, refresh the branch, run cheap preflight,
         destroy it on success, and keep it on failure for debugging.
shell    SSH into the active sandbox.
destroy  Destroy the active sandbox.
EOF
    exit 2
    ;;
esac
