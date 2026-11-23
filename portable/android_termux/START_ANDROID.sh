#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
APP="$(cd "$(dirname "$0")" && pwd -P)"
cd "$APP"
if ! command -v python >/dev/null 2>&1; then
  if command -v pkg >/dev/null 2>&1; then
    echo "First-run: installing Python using Termux's package manager (internet required)."
    pkg install -y python
  else
    echo "This requires Android Termux; not a native APK." >&2
    exit 2
  fi
fi
python -c 'import sys,sqlite3,ssl;assert sys.version_info >= (3,10)'
mkdir -p "$APP/data"
chmod 700 "$APP/data"
if [ -z "$(printenv MERLIN_LLAMA_SERVER || true)" ] && command -v llama-server >/dev/null 2>&1; then
  export MERLIN_LLAMA_SERVER="$(command -v llama-server)"
fi
echo "Merlin Studio: http://127.0.0.1:8771/studio/"
echo "Offline /help and workspace commands work without model weights."
echo "Optional local AI installation: bash INSTALL_ANDROID_MODEL.sh"
exec python "$APP/server.py" --port 8771 --open "$@"
