#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
command -v pkg >/dev/null 2>&1 || { echo 'Termux required' >&2; exit 2; }
command -v curl >/dev/null 2>&1 || pkg install -y curl
command -v sha256sum >/dev/null 2>&1 || pkg install -y coreutils
if ! command -v llama-server >/dev/null 2>&1; then
  pkg install -y llama-cpp
fi
command -v llama-server >/dev/null 2>&1 || { echo 'llama-server was not installed; check Termux repository availability' >&2; exit 3; }
mkdir -p models
target="models/merlin-local.gguf"
expected="74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db"
url="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/9217f5db79a29953eb74d5343926648285ec7e67/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true"
if [ -f "$target" ] && printf '%s  %s\n' "$expected" "$target" | sha256sum --check --status; then
  echo 'Model already verified.'
else
  temp="$(mktemp "$PWD/models/.download.XXXXXXXX")"
  trap 'rm -f "$temp"' EXIT
  curl --fail --location --retry 2 --connect-timeout 20 --max-time 1500 "$url" -o "$temp"
  printf '%s  %s\n' "$expected" "$temp" | sha256sum --check
  mv -f "$temp" "$target"
  chmod 600 "$target"
  trap - EXIT
fi
echo "Model verified. Restart Merlin with: bash START_ANDROID.sh"
