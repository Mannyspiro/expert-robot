#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_REPO="${MODEL_REPO:-bartowski/NousResearch_NousCoder-14B-GGUF}"
MODEL_FILE="${MODEL_FILE:-NousCoder-14B-Q4_K_M.gguf}"
MODEL_DIR="${MODEL_DIR:-${ROOT}/models/hermes_coder}"
MIN_FREE_GB="${MIN_FREE_GB:-11}"
mkdir -p "$MODEL_DIR"
free_kb="$(df -Pk "$MODEL_DIR" | awk 'NR==2 {print $4}')"
free_gb=$((free_kb / 1024 / 1024))
if (( free_gb < MIN_FREE_GB )); then
  echo "Insufficient free disk: ${free_gb} GiB available; need ${MIN_FREE_GB} GiB." >&2
  exit 2
fi
if ! command -v hf >/dev/null 2>&1; then
  python3 -m pip install --user --upgrade "huggingface_hub[cli]"
fi
command -v hf >/dev/null 2>&1 || { echo "Hugging Face 'hf' command unavailable." >&2; exit 3; }
echo "Downloading ${MODEL_REPO}/${MODEL_FILE} into ${MODEL_DIR}"
hf download "$MODEL_REPO" "$MODEL_FILE" --local-dir "$MODEL_DIR"
test -s "${MODEL_DIR}/${MODEL_FILE}"
printf 'Model ready: %s\n' "${MODEL_DIR}/${MODEL_FILE}"
