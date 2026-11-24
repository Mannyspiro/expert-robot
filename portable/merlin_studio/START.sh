#!/bin/sh
set -eu
studio_directory=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
cd "$studio_directory"
if [ -e "$studio_directory/OFFLINE_PROFILE_MANIFEST.json" ]; then
    if [ ! -f "$studio_directory/OFFLINE_PLATFORM" ] || [ -L "$studio_directory/OFFLINE_PLATFORM" ]; then
        printf '%s\n' 'Merlin offline platform marker is missing. Extract the complete verified package again.' >&2
        exit 1
    fi
    IFS= read -r studio_platform < "$studio_directory/OFFLINE_PLATFORM"
    case "$(uname -s):$(uname -m):$studio_platform" in
        Linux:x86_64:linux-x86_64|Linux:aarch64:linux-aarch64) ;;
        *) printf '%s\n' 'This offline package does not match this host. Use the Linux x86_64 or aarch64 package for your CPU.' >&2; exit 1 ;;
    esac
fi
if [ -x "$studio_directory/runtime/python/bin/python3" ]; then
    studio_python="$studio_directory/runtime/python/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    studio_python=$(command -v python3)
elif command -v python >/dev/null 2>&1; then
    studio_python=$(command -v python)
else
    printf '%s\n' 'Merlin Studio requires Python 3.10 or newer. Install Python, then run START.sh again.' >&2
    exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
"$studio_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Merlin Studio requires Python 3.10 or newer.")' || {
    printf '%s\n' 'The selected Python runtime cannot start. Check package architecture, executable permissions, and compatible Linux system libraries.' >&2
    exit 1
}
if [ "${1-}" = --check ]; then
    shift
    exec "$studio_python" "$studio_directory/linux_preflight.py" --root "$studio_directory" --probe-binary "$@"
fi
if [ -e "$studio_directory/OFFLINE_PROFILE_MANIFEST.json" ]; then
    # A failed optional engine must not hide the offline workspace. The model
    # launcher separately enforces the static compatibility gate.
    "$studio_python" "$studio_directory/linux_preflight.py" --root "$studio_directory" --probe-binary --quiet --startup "$@" || true
fi
if [ "${1-}" = --headless ]; then
    shift
    exec "$studio_python" "$studio_directory/server.py" --port 8771 "$@"
fi
exec "$studio_python" "$studio_directory/server.py" --port 8771 --open "$@"
