#!/usr/bin/env bash
set -euo pipefail

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

mkdir -p "$ROOT/source" "$ROOT/out"
printf 'core-data\n' > "$ROOT/source/core.txt"

scripts/collar_vault.sh keygen "$ROOT/key"
scripts/collar_vault.sh seal "$ROOT/key" "$ROOT/source" "$ROOT/core.enc"
scripts/collar_vault.sh unseal "$ROOT/key" "$ROOT/core.enc" "$ROOT/out"

cmp "$ROOT/source/core.txt" "$ROOT/out/core.txt"

cp "$ROOT/core.enc" "$ROOT/tampered.enc"
cp "$ROOT/core.enc.hmac" "$ROOT/tampered.enc.hmac"
printf 'x' >> "$ROOT/tampered.enc"

if scripts/collar_vault.sh unseal "$ROOT/key" "$ROOT/tampered.enc" "$ROOT/tampered-out" 2>/dev/null; then
  echo "tampered core unexpectedly decrypted" >&2
  exit 1
fi

scripts/collar_vault.sh destroy-key "$ROOT/key"
test ! -e "$ROOT/key"

echo "collar vault smoke: PASS"
