#!/usr/bin/env bash
set -euo pipefail
base=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
portable="${MERLIN_PORTABLE:-$base/Merlin_Chip_USB}"
cache="${MERLIN_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/merlin-ai-os}"
state="${MERLIN_OS_STATE:-${XDG_STATE_HOME:-$HOME/.local/state}/merlin-ai-os}"
export OPENBLAS_NUM_THREADS="${MERLIN_BLAS_THREADS:-2}"
umask 077
mkdir -p "$cache" "$state"
set -- "$@" --portable "$portable" --state "$state"
digest=$(<"$portable/runtime-x86_64.sha256")
if [[ ! "$digest" =~ ^[a-f0-9]{64}$ ]] || [[ $(sha256sum "$portable/runtime-x86_64.tar.gz" | cut -d' ' -f1) != "$digest" ]]; then
  echo 'Portable runtime checksum mismatch.' >&2
  exit 1
fi
runtime="$cache/$digest"
if [[ ! -x "$runtime/python/bin/python3.12" ]]; then
  stage=$(mktemp -d "$cache/.stage.XXXXXXXX")
  trap 'rm -rf -- "$stage"' EXIT
  tar -xzf "$portable/runtime-x86_64.tar.gz" -C "$stage"
  if ! mv -T "$stage" "$runtime" 2>/dev/null; then
    [[ -x "$runtime/python/bin/python3.12" ]] || exit 1
    rm -rf -- "$stage"
  fi
fi
export MERLIN_RUNTIME_DIR="$runtime" MERLIN_CACHE_DIR="$cache"
exec "$runtime/python/bin/python3.12" -B -E -s "$base/aios.py" "$@"
