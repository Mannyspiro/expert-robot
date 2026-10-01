#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  collar_vault.sh keygen <key-file>
  collar_vault.sh seal <key-file> <source-dir> <sealed-file>
  collar_vault.sh unseal <key-file> <sealed-file> <dest-dir>
  collar_vault.sh destroy-key <key-file>

The key file contains two random 256-bit keys and should live on tmpfs
(prefer /dev/shm). No user passkey is required.
EOF
}

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 2
  }
}

keygen() {
  local key_file="$1"
  require openssl
  umask 077
  mkdir -p "$(dirname "$key_file")"
  {
    printf 'ENC_KEY='
    openssl rand -hex 32
    printf 'MAC_KEY='
    openssl rand -hex 32
  } > "$key_file"
  chmod 600 "$key_file"
}

load_keys() {
  local key_file="$1"
  test -f "$key_file"
  # shellcheck disable=SC1090
  source "$key_file"
  test "${#ENC_KEY}" -eq 64
  test "${#MAC_KEY}" -eq 64
}

seal() {
  local key_file="$1" src="$2" sealed="$3"
  require openssl
  require tar
  load_keys "$key_file"
  test -d "$src"
  mkdir -p "$(dirname "$sealed")"
  local tmp
  tmp="$(mktemp "${sealed}.tmp.XXXXXX")"
  trap 'if [ -n "${tmp:-}" ]; then rm -f -- "$tmp"; fi' EXIT

  tar -C "$src" -cf - . |
    openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
      -pass fd:3 -out "$tmp" 3<<<"$ENC_KEY"

  local mac
  mac="$(openssl dgst -sha256 -mac HMAC -macopt "hexkey:$MAC_KEY" "$tmp" | awk '{print $NF}')"
  mv "$tmp" "$sealed"
  printf '%s\n' "$mac" > "${sealed}.hmac"
  chmod 600 "$sealed" "${sealed}.hmac"
  trap - EXIT
}

unseal() {
  local key_file="$1" sealed="$2" dest="$3"
  require openssl
  require tar
  load_keys "$key_file"
  test -f "$sealed"
  test -f "${sealed}.hmac"

  local expected actual
  expected="$(tr -d '\r\n' < "${sealed}.hmac")"
  actual="$(openssl dgst -sha256 -mac HMAC -macopt "hexkey:$MAC_KEY" "$sealed" | awk '{print $NF}')"
  test "$expected" = "$actual" || {
    echo "sealed core integrity check failed" >&2
    exit 40
  }

  test ! -e "$dest" || {
    test -d "$dest"
    test -z "$(find "$dest" -mindepth 1 -maxdepth 1 -print -quit)"
  }
  mkdir -p "$dest"
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass fd:3 -in "$sealed" 3<<<"$ENC_KEY" |
    tar -C "$dest" -xf -
}

destroy_key() {
  local key_file="$1"
  if [ -f "$key_file" ]; then
    chmod 600 "$key_file" || true
    : > "$key_file" || true
    rm -f "$key_file"
  fi
}

case "${1:-}" in
  keygen)
    [ "$#" -eq 2 ] || { usage; exit 2; }
    keygen "$2"
    ;;
  seal)
    [ "$#" -eq 4 ] || { usage; exit 2; }
    seal "$2" "$3" "$4"
    ;;
  unseal)
    [ "$#" -eq 4 ] || { usage; exit 2; }
    unseal "$2" "$3" "$4"
    ;;
  destroy-key)
    [ "$#" -eq 2 ] || { usage; exit 2; }
    destroy_key "$2"
    ;;
  *)
    usage
    exit 2
    ;;
esac
