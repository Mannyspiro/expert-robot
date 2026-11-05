#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${MERLIN_HUD_ENV_FILE:-${HOME}/.local/share/merlin/merlin-hud.env}"

if [ ! -f "$env_file" ]; then
  echo "Merlin canonical stores are not initialized."
  echo "Run: python3 scripts/init_merlin_dashboard_stores.py"
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$env_file"
set +a

export PYTHONPATH="$repo_root/python${PYTHONPATH:+:$PYTHONPATH}"
cd "$repo_root"
exec python3 -m merlin.app --port "${MERLIN_PORT:-8765}"
