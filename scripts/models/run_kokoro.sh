#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_DIR="${MODEL_DIR:-${ROOT}/models/voice/kokoro}"
export KOKORO_MODEL="${KOKORO_MODEL:-${MODEL_DIR}/kokoro-v1.0.onnx}"
export KOKORO_VOICES="${KOKORO_VOICES:-${MODEL_DIR}/voices-v1.0.bin}"
export KOKORO_HOST="${KOKORO_HOST:-127.0.0.1}"
export KOKORO_PORT="${KOKORO_PORT:-8880}"
python3 -m pip install --user -r "${ROOT}/python/voice/requirements.txt"
exec python3 "${ROOT}/python/voice/kokoro_server.py"
