#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: prepare_collared_generation.sh <trusted-source-dir> <sealed-file> <key-file-under-/dev/shm>" >&2
}

[ "$#" -eq 3 ] || { usage; exit 2; }
SOURCE="$(readlink -f "$1")"
SEALED="$2"
KEY="$3"

test -d "$SOURCE"
case "$KEY" in
  /dev/shm/*) ;;
  *) echo "generation key must be under /dev/shm" >&2; exit 42 ;;
esac

mkdir -p "$(dirname "$SEALED")"
test ! -e "$KEY" || { echo "refusing to reuse existing generation key" >&2; exit 42; }
test ! -e "$SEALED" || { echo "refusing to overwrite existing sealed generation" >&2; exit 42; }

scripts/collar_vault.sh keygen "$KEY"
trap 'scripts/collar_vault.sh destroy-key "$KEY" >/dev/null 2>&1 || true' ERR INT TERM
scripts/collar_vault.sh seal "$KEY" "$SOURCE" "$SEALED"
chmod 600 "$KEY" "$SEALED" "$SEALED.hmac"

echo "sealed generation prepared; keep the one-use key on tmpfs and outside the candidate workspace"
