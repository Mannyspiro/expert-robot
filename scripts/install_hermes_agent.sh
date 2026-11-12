#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HERMES_AGENT_DIR:-${ROOT}/.tools/hermes-agent}"
REF="${HERMES_AGENT_REF:-main}"
INSTALL_CLI="${1:-}"
if [[ -e "$DEST/.git" ]]; then
  echo "Hermes Agent source exists; updating to requested ref."
  git -C "$DEST" fetch --depth 1 origin "$REF"
  git -C "$DEST" checkout --detach FETCH_HEAD
else
  mkdir -p "$(dirname "$DEST")"
  git clone --filter=blob:none --depth 1 --branch "$REF" https://github.com/NousResearch/hermes-agent.git "$DEST"
fi
printf 'Hermes Agent source revision: '
git -C "$DEST" rev-parse HEAD
printf 'Hermes Agent source path: %s\n' "$DEST"
if [[ "$INSTALL_CLI" == "--install" ]]; then
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o "$tmp"
  bash "$tmp"
else
  echo "Source downloaded only. Pass --install to run the upstream user-level installer."
fi
