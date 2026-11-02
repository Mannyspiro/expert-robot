#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "\${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_FILE="\${MODEL_FILE:-\${ROOT}/models/hermes_coder/NousCoder-14B-Q4_K_M.gguf}"
HOST="\${HOST:-127.0.0.1}"
PORT="\${PORT:-8080}"
CTX_SIZE="\${CTX_SIZE:-65536}"
THREADS="\${THREADS:-$(nproc 2>/dev/null || echo 4)}"
command -v llama-server >/dev/null 2>&1 || { echo "Install llama.cpp (llama-server) first." >&2; exit 2; }
[[ -s "$MODEL_FILE" ]] || { echo "Model not found: $MODEL_FILE. Run scripts/models/download_nouscoder.sh." >&2; exit 3; }
exec llama-server --model "$MODEL_FILE" --host "$HOST" --port "$PORT" --ctx-size "$CTX_SIZE" --threads "$THREADS"
