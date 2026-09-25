#!/usr/bin/env bash
set -euo pipefail

say() {
  printf '[railway-bootstrap] %s\n' "$*"
}

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
else
  SUDO=""
fi

missing=()
for cmd in git python3 cmake ninja c++; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done

if [ "${#missing[@]}" -gt 0 ]; then
  if ! command -v apt-get >/dev/null 2>&1; then
    say "missing tools: ${missing[*]}"
    say "apt-get is unavailable; install build-essential cmake ninja-build libsqlite3-dev git curl python3 manually."
    exit 2
  fi

  say "installing C++/SQLite/build prerequisites"
  $SUDO apt-get update
  $SUDO apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    libsqlite3-dev \
    ninja-build \
    python3
fi

if ! command -v lake >/dev/null 2>&1; then
  if ! command -v curl >/dev/null 2>&1; then
    say "curl is required to install elan/Lean"
    exit 2
  fi

  say "installing elan for the repo-pinned Lean toolchain"
  curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    | sh -s -- -y --default-toolchain none

  export PATH="$HOME/.elan/bin:$PATH"
fi

cpu="$(nproc 2>/dev/null || echo 1)"
mem_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)"
mem_mb="$((mem_kb / 1024))"

say "worker detected: ${cpu} CPU(s), ${mem_mb} MiB RAM"
say "Lean: $(command -v lake || true)"
say "CMake: $(cmake --version | head -n1)"
say "Ninja: $(ninja --version)"
say "bootstrap complete"
