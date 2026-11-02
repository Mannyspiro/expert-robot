#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "\${BASH_SOURCE[0]}")/../.." && pwd)"
MODEL_DIR="\${MODEL_DIR:-\${ROOT}/models/voice/kokoro}"
BASE_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1"
mkdir -p "$MODEL_DIR"
download() {
  local name="$1" target="\${MODEL_DIR}/$1"
  if [[ -s "$target" ]]; then echo "Already present: $target"; return; fi
  curl --fail --location --retry 3 --retry-delay 2 "\${BASE_URL}/\${name}" --output "\${target}.part"
  mv "\${target}.part" "$target"
  test -s "$target"
}
download "kokoro-v1.0.onnx"
download "voices-v1.0.bin"
echo "Kokoro model and voice pack ready in $MODEL_DIR"
