#!/usr/bin/env bash
set -euo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends ca-certificates git curl cmake ninja-build g++ make python3 tar gzip coreutils binutils file procps util-linux
BASE="$GITHUB_WORKSPACE"
WORK="$BASE/build-work"
SOURCE="$WORK/merlin-source"
HOME_SAFE="$WORK/home"
mkdir -p "$WORK" "$HOME_SAFE" "$BASE/portable-package" "$BASE/release-evidence"
# Run fetched source tooling without GitLab credentials or account configuration.
clean() { env -i PATH="$PATH" HOME="$HOME_SAFE" LANG=C.UTF-8 LC_ALL=C.UTF-8 "$@"; }
SOURCE_SHA=fb20f80293772f8b783b33344dbd7c06740283bd
LLAMA_SHA=44d50873b56b568c28ef2ad8d6445069feaa9fbd
MODEL_REV=9217f5db79a29953eb74d5343926648285ec7e67
MODEL_SHA=74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
PY_TAR_SHA=ac0b758b6ae4ba1cb87f7091eb6bb17c9a383a9bcdb5c18493cdd4f34e35ae8c
printf 'merlin=%s\nllama.cpp=%s\nmodel_revision=%s\nmodel_sha256=%s\npython_archive_sha256=%s\n' "$SOURCE_SHA" "$LLAMA_SHA" "$MODEL_REV" "$MODEL_SHA" "$PY_TAR_SHA" > "$BASE/release-evidence/source-pins.txt"
test "$(uname -m)" = x86_64
clean git clone --quiet --filter=blob:none --no-checkout https://github.com/Mannyspiro/expert-robot.git "$SOURCE"
clean git -C "$SOURCE" fetch --quiet --depth 1 origin "$SOURCE_SHA"
clean git -C "$SOURCE" checkout --quiet --detach "$SOURCE_SHA"
test "$(clean git -C "$SOURCE" rev-parse HEAD)" = "$SOURCE_SHA"
rm -rf "$SOURCE/.git"
clean python3 "$SOURCE/portable/build_portable.py" --output "$WORK/Merlin-Studio-source.zip"
clean python3 "$SOURCE/scripts/verify_portable.py" "$WORK/Merlin-Studio-source.zip"
clean git clone --quiet --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$WORK/llama-source"
clean git -C "$WORK/llama-source" fetch --quiet --depth 1 origin "$LLAMA_SHA"
clean git -C "$WORK/llama-source" checkout --quiet --detach "$LLAMA_SHA"
test "$(clean git -C "$WORK/llama-source" rev-parse HEAD)" = "$LLAMA_SHA"
rm -rf "$WORK/llama-source/.git"
clean cmake -S "$WORK/llama-source" -B "$WORK/llama-build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF
clean cmake --build "$WORK/llama-build" --target llama-server -j 2
LLAMA_BIN="$WORK/llama-build/bin/llama-server"
test -x "$LLAMA_BIN"
ldd "$LLAMA_BIN" > "$BASE/release-evidence/llama-dynamic-dependencies.txt"
! grep -q 'not found' "$BASE/release-evidence/llama-dynamic-dependencies.txt"
LLAMA_BIN_SHA="$(sha256sum "$LLAMA_BIN" | cut -d ' ' -f 1)"
PY_ARCHIVE="$WORK/cpython-install-only.tar.gz"
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.11.18%2B20261110-x86_64-unknown-linux-gnu-install_only.tar.gz" -o "$PY_ARCHIVE"
echo "$PY_TAR_SHA  $PY_ARCHIVE" | sha256sum --check
mkdir -p "$WORK/runtime"
tar -xzf "$PY_ARCHIVE" -C "$WORK/runtime"
PY_ROOT="$WORK/runtime/python"
test -x "$PY_ROOT/bin/python3"
PY_BIN="$(readlink -f "$PY_ROOT/bin/python3")"
PY_BIN_SHA="$(sha256sum "$PY_BIN" | cut -d ' ' -f 1)"
clean "$PY_ROOT/bin/python3" -c 'import ssl,sqlite3,hashlib,http.server;print("standalone CPython: PASS")'
GGUF="$WORK/qwen2.5-0.5b-instruct-q4_k_m.gguf"
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 1000 "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/$MODEL_REV/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true" -o "$GGUF"
test "$(stat -c %s "$GGUF")" -eq 491400032
echo "$MODEL_SHA  $GGUF" | sha256sum --check
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 90 "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/raw/$MODEL_REV/LICENSE" -o "$WORK/model-license.txt"
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 90 "https://raw.githubusercontent.com/python/cpython/v3.11.18/LICENSE" -o "$WORK/python-license.txt"
cp "$WORK/llama-source/LICENSE" "$WORK/llama-license.txt"
grep -q 'Apache License' "$WORK/model-license.txt"
grep -q 'MIT License' "$WORK/llama-license.txt"
test -s "$WORK/python-license.txt"
ZIP="$BASE/portable-package/Merlin-Studio-linux-x86_64-offline-Qwen0.5B.zip"
clean python3 "$SOURCE/portable/build_offline_profile.py" \
  --studio-zip "$WORK/Merlin-Studio-source.zip" --python-root "$PY_ROOT" \
  --python-sha256 "$PY_BIN_SHA" --llama-server "$LLAMA_BIN" \
  --llama-sha256 "$LLAMA_BIN_SHA" --gguf-model "$GGUF" \
  --gguf-sha256 "$MODEL_SHA" --model-license "$WORK/model-license.txt" \
  --inference-license "$WORK/llama-license.txt" \
  --python-license "$WORK/python-license.txt" --target linux-x86_64 \
  --model-origin "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/tree/$MODEL_REV" \
  --inference-origin "https://github.com/ggml-org/llama.cpp/tree/$LLAMA_SHA" \
  --python-origin "https://github.com/astral-sh/python-build-standalone/releases/tag/20261110" \
  --output "$ZIP"
clean python3 "$SOURCE/scripts/verify_offline_profile.py" "$ZIP" > "$BASE/release-evidence/offline-zip-verification.json"
sha256sum "$ZIP" > "$BASE/release-evidence/ZIP_SHA256SUMS.txt"
clean python3 "$SOURCE/scripts/extract_offline_profile.py" "$ZIP" --destination "$WORK/extracted"
APP="$WORK/extracted/Merlin_Studio"
BUNDLED_PY="$APP/runtime/python/bin/python3"
clean "$BUNDLED_PY" -c 'import ssl,sqlite3,http.server;print("extracted runtime: PASS")'
clean "$BUNDLED_PY" "$APP/PROFILE_VERIFY.py" "$ZIP" > "$BASE/release-evidence/extracted-profile-verification.json"
setsid env -i PATH="$PATH" HOME="$HOME_SAFE" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
 "$BUNDLED_PY" "$APP/server.py" --port 18771 --data-dir "$WORK/smoke-state" \
 > "$BASE/release-evidence/native-studio-server.log" 2>&1 &
APP_PID=$!
cleanup() { kill -- -"$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT
clean "$BUNDLED_PY" "$BASE/scripts/merlin/native_self_contained_smoke.py" > "$BASE/release-evidence/native-smoke.json"
cleanup
wait "$APP_PID" 2>/dev/null || true
trap - EXIT
printf '%s\n' 'All test evidence scoped to a fresh Linux x86_64 runner.' \
 'Model quality, redistribution review, other OS and long-term production qualification remain open.' \
 > "$BASE/release-evidence/QUALIFICATION_SCOPE.txt"
