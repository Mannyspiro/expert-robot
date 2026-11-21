#!/bin/sh
set -eu
studio_directory=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
cd "$studio_directory"
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
"$studio_python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Merlin Studio requires Python 3.10 or newer.")'
exec "$studio_python" "$studio_directory/server.py" --port 8771 --open "$@"
