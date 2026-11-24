#!/usr/bin/env bash
set -euo pipefail
umask 077
SOURCE_SHA="${MERLIN_EXACT_SOURCE_SHA:?supply the exact checked-out source commit}"
[[ "$SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid exact source commit" >&2; exit 1; }
BASE="$(cd -- "${GITHUB_WORKSPACE:?supply the checked-out workspace}" && pwd -P)"
command -v git >/dev/null || { echo "Preprovisioned git is required" >&2; exit 1; }
test "$(git -C "$BASE" rev-parse --show-toplevel)" = "$BASE"
if test "$(git -C "$BASE" rev-parse HEAD)" != "$SOURCE_SHA"; then
  echo "Checkout does not match the supplied exact source commit" >&2
  exit 1
fi
test -z "$(git -C "$BASE" status --porcelain --untracked-files=no)" || {
  echo "Tracked source must be clean before packaging" >&2; exit 1;
}
SOURCE_TREE="$(git -C "$BASE" rev-parse "$SOURCE_SHA^{tree}")"
[[ "$SOURCE_TREE" =~ ^[0-9a-f]{40}$ ]]
# The runner image must provide build tools; this script installs nothing.
for required in curl cmake ninja gcc g++ make python3 tar gzip sha256sum readlink readelf ldd stat setsid env mkdir rm cp grep cut uname; do
  command -v "$required" >/dev/null || {
    echo "Missing preprovisioned build tool: $required" >&2; exit 1;
  }
done
ARCH="${MERLIN_TARGET_ARCH:?supply x86_64 or aarch64 from the ordinary Ubuntu runner matrix}"
case "$ARCH" in
  x86_64)
    PY_TAR_SHA=ac0b758b6ae4ba1cb87f7091eb6bb17c9a383a9bcdb5c18493cdd4f34e35ae8c
    PY_TAR_BYTES=49244720
    CPU_OPTIONS=(-DGGML_SSE42=ON -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_BMI2=ON -DGGML_FMA=ON -DGGML_F16C=ON -DGGML_AVX512=OFF)
    ;;
  aarch64)
    PY_TAR_SHA=623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861
    PY_TAR_BYTES=49469868
    CPU_OPTIONS=(-DGGML_CPU_ARM_ARCH=armv8-a)
    ;;
  *) echo "Unsupported native Linux architecture" >&2; exit 1 ;;
esac
test "$(uname -m)" = "$ARCH"
TARGET="linux-$ARCH"
WORK="$BASE/build-work"
SOURCE="$WORK/merlin-source"
HOME_SAFE="$WORK/home"
for owned in "$WORK" "$BASE/portable-package" "$BASE/portable-parts" "$BASE/release-evidence"; do
  if test -e "$owned" || test -L "$owned"; then
    echo "Build output paths must be new" >&2; exit 1
  fi
done
mkdir -p "$SOURCE" "$HOME_SAFE" "$BASE/portable-package" "$BASE/release-evidence"
# Run source tooling without inherited credentials or account configuration.
clean() { env -i PATH="$PATH" HOME="$HOME_SAFE" LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 "$@"; }
LLAMA_SHA=44d50873b56b568c28ef2ad8d6445069feaa9fbd
MODEL_REV=91cad51170dc346986eccefdc2dd33a9da36ead9
MODEL_SHA=6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
printf 'merlin=%s\nmerlin_tree=%s\nllama.cpp=%s\nmodel_revision=%s\nmodel_sha256=%s\npython_archive_sha256=%s\n' "$SOURCE_SHA" "$SOURCE_TREE" "$LLAMA_SHA" "$MODEL_REV" "$MODEL_SHA" "$PY_TAR_SHA" > "$BASE/release-evidence/source-pins.txt"
printf 'target=%s\npython_archive_bytes=%s\n' "$TARGET" "$PY_TAR_BYTES" >> "$BASE/release-evidence/source-pins.txt"
clean git -C "$BASE" archive --format=tar "$SOURCE_SHA" | tar -xf - -C "$SOURCE"
clean python3 "$SOURCE/portable/build_portable.py" --output "$WORK/Merlin-Studio-source.zip"
clean python3 "$SOURCE/scripts/verify_portable.py" "$WORK/Merlin-Studio-source.zip"
clean git clone --quiet --filter=blob:none --no-checkout https://github.com/ggml-org/llama.cpp.git "$WORK/llama-source"
clean git -C "$WORK/llama-source" fetch --quiet --depth 1 origin "$LLAMA_SHA"
clean git -C "$WORK/llama-source" checkout --quiet --detach "$LLAMA_SHA"
test "$(clean git -C "$WORK/llama-source" rev-parse HEAD)" = "$LLAMA_SHA"
rm -rf "$WORK/llama-source/.git"
# Studio supplies the UI. Disable both upstream UI modes so this exact source
# cannot fetch mutable prebuilt UI assets (including the upstream latest fallback).
test ! -e "$WORK/llama-source/ui/apps/chat/dist"
clean cmake -S "$WORK/llama-source" -B "$WORK/llama-build" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_CUDA=OFF -DGGML_VULKAN=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF "${CPU_OPTIONS[@]}"
grep -Fx 'LLAMA_BUILD_UI:BOOL=OFF' "$WORK/llama-build/CMakeCache.txt" > "$BASE/release-evidence/llama-ui-build-options.txt"
grep -Fx 'LLAMA_USE_PREBUILT_UI:BOOL=OFF' "$WORK/llama-build/CMakeCache.txt" >> "$BASE/release-evidence/llama-ui-build-options.txt"
clean cmake --build "$WORK/llama-build" --target llama-server -j 2
LLAMA_BIN="$WORK/llama-build/bin/llama-server"
test -x "$LLAMA_BIN"
ldd "$LLAMA_BIN" > "$BASE/release-evidence/llama-dynamic-dependencies.txt"
! grep -q 'not found' "$BASE/release-evidence/llama-dynamic-dependencies.txt"
LLAMA_BIN_SHA="$(sha256sum "$LLAMA_BIN" | cut -d ' ' -f 1)"
PY_ARCHIVE="$WORK/cpython-install-only.tar.gz"
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 "https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.11.18%2B20261110-$ARCH-unknown-linux-gnu-install_only.tar.gz" -o "$PY_ARCHIVE"
test "$(stat -c %s "$PY_ARCHIVE")" -eq "$PY_TAR_BYTES"
echo "$PY_TAR_SHA  $PY_ARCHIVE" | sha256sum --check
clean python3 - "$PY_ARCHIVE" "$PY_TAR_SHA" "$BASE/release-evidence/runtime-cache-exclusions.json" <<'PY'
import hashlib
import json
from pathlib import PurePosixPath
import sys
import tarfile

archive, expected, report = sys.argv[1:]
excluded = []
with tarfile.open(archive, "r:gz") as source:
    for member in source:
        if "__pycache__" not in PurePosixPath(member.name).parts:
            continue
        if member.isdir():
            continue
        if not member.isfile() or not member.name.endswith(".pyc"):
            raise ValueError("Unexpected member in pinned runtime bytecode cache")
        with source.extractfile(member) as cached:
            digest = hashlib.file_digest(cached, "sha256").hexdigest()
        excluded.append({"path": member.name, "bytes": member.size, "sha256": digest})
with open(report, "x", encoding="utf-8") as output:
    json.dump({"schema": "merlin-runtime-cache-exclusions/1",
               "verified_archive_sha256": expected,
               "extraction_exclude": "*/__pycache__",
               "excluded_files": excluded,
               "excluded_bytes": sum(item["bytes"] for item in excluded),
               "source_and_license_files_preserved": True}, output, indent=2, sort_keys=True)
    output.write("\n")
PY
mkdir -p "$WORK/runtime"
# The verified standalone archive includes bytecode caches. Preserve its source
# and notices, omit only those caches, and keep the packager's rejection intact.
tar --exclude='*/__pycache__' -xzf "$PY_ARCHIVE" -C "$WORK/runtime"
PY_ROOT="$WORK/runtime/python"
test -x "$PY_ROOT/bin/python3"
PY_BIN="$(readlink -f "$PY_ROOT/bin/python3")"
PY_BIN_SHA="$(sha256sum "$PY_BIN" | cut -d ' ' -f 1)"
clean "$PY_ROOT/bin/python3" -c 'import ssl,sqlite3,hashlib,http.server;print("standalone CPython: PASS")'
clean python3 "$SOURCE/scripts/merlin/linux_build_requirements.py" \
  --build-directory "$WORK/llama-build" --target "$TARGET" \
  --engine-sha256 "$LLAMA_BIN_SHA" --python-sha256 "$PY_BIN_SHA" \
  --requirements "$WORK/linux-runtime-requirements.json" \
  --evidence "$BASE/release-evidence/llama-build-configuration.json"
GGUF="$WORK/qwen2.5-1.5b-instruct-q4_k_m.gguf"
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 1000 "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/$MODEL_REV/qwen2.5-1.5b-instruct-q4_k_m.gguf?download=true" -o "$GGUF"
test "$(stat -c %s "$GGUF")" -eq 1117320736
echo "$MODEL_SHA  $GGUF" | sha256sum --check
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 90 "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/raw/$MODEL_REV/LICENSE" -o "$WORK/model-license.txt"
echo "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e  $WORK/model-license.txt" | sha256sum --check
clean curl --fail --location --retry 3 --connect-timeout 20 --max-time 90 "https://raw.githubusercontent.com/python/cpython/v3.11.18/LICENSE" -o "$WORK/python-license.txt"
cp "$WORK/llama-source/LICENSE" "$WORK/llama-license.txt"
grep -q 'Apache License' "$WORK/model-license.txt"
grep -q 'MIT License' "$WORK/llama-license.txt"
test -s "$WORK/python-license.txt"
ZIP="$BASE/portable-package/Merlin-Studio-$TARGET-offline-Qwen1.5B.zip"
clean python3 "$SOURCE/portable/build_offline_profile.py" \
  --studio-zip "$WORK/Merlin-Studio-source.zip" --python-root "$PY_ROOT" \
  --python-sha256 "$PY_BIN_SHA" --llama-server "$LLAMA_BIN" \
  --llama-sha256 "$LLAMA_BIN_SHA" --gguf-model "$GGUF" \
  --gguf-sha256 "$MODEL_SHA" --model-license "$WORK/model-license.txt" \
  --inference-license "$WORK/llama-license.txt" \
  --python-license "$WORK/python-license.txt" --target "$TARGET" \
  --runtime-requirements "$WORK/linux-runtime-requirements.json" \
  --model-origin "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/$MODEL_REV" \
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
clean sh "$APP/START.sh" --check --data-dir "$WORK/smoke-state" > "$BASE/release-evidence/linux-host-preflight.json"
setsid env -i PATH="$PATH" HOME="$HOME_SAFE" LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
 sh "$APP/START.sh" --headless --port 18771 --data-dir "$WORK/smoke-state" \
 > "$BASE/release-evidence/native-studio-server.log" 2>&1 &
APP_PID=$!
cleanup() { kill -- -"$APP_PID" 2>/dev/null || true; }
trap cleanup EXIT
clean "$BUNDLED_PY" "$SOURCE/scripts/merlin/native_self_contained_smoke.py" > "$BASE/release-evidence/native-smoke.json"
# Separate real-output observability for the GUI. The arithmetic acceptance
# above is unchanged and must already pass before this public prompt is sent.
clean "$BUNDLED_PY" "$SOURCE/scripts/merlin/studio_live_stream_trace.py" \
  --profile-manifest "$APP/OFFLINE_PROFILE_MANIFEST.json" --model-sha256 "$MODEL_SHA" \
  --source-commit "$SOURCE_SHA" --source-tree "$SOURCE_TREE" \
  > "$BASE/release-evidence/studio-ui-live-trace.json"
clean "$BUNDLED_PY" "$SOURCE/scripts/merlin/studio_restart_smoke.py" capture \
  --state-dir "$WORK/smoke-state" --checkpoint "$WORK/restart-checkpoint.json"
cleanup
wait "$APP_PID" 2>/dev/null || true
setsid env -i PATH="$PATH" HOME="$HOME_SAFE" LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 \
 sh "$APP/START.sh" --headless --port 18771 --data-dir "$WORK/smoke-state" \
 >> "$BASE/release-evidence/native-studio-server.log" 2>&1 &
APP_PID=$!
clean "$BUNDLED_PY" "$SOURCE/scripts/merlin/studio_restart_smoke.py" verify \
  --state-dir "$WORK/smoke-state" --checkpoint "$WORK/restart-checkpoint.json" \
  > "$BASE/release-evidence/studio-restart-smoke.json"
cleanup
wait "$APP_PID" 2>/dev/null || true
trap - EXIT
printf '%s\n' "Native acceptance ran through extracted START.sh on a fresh $TARGET Ubuntu 24.04 runner." \
 'Clean environment and disabled Studio network tools were used; OS-enforced network isolation was not performed.' \
 'Model quality, redistribution review, target OCI host qualification, other OS and long-term production qualification remain open.' \
 > "$BASE/release-evidence/QUALIFICATION_SCOPE.txt"
# Transport the already accepted ZIP in three ordinary bounded artifacts.
# Reassembly must reproduce the original full ZIP digest before verification.
clean python3 "$SOURCE/scripts/merlin/offline_delivery.py" split \
  --archive "$ZIP" --parts-dir "$BASE/portable-parts" --evidence-dir "$BASE/release-evidence" \
  --source-commit "$SOURCE_SHA" --source-tree "$SOURCE_TREE"
