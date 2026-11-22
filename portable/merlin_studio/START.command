#!/bin/sh
set -eu
studio_directory=$(CDPATH= cd -P "$(dirname "$0")" && pwd)
exec /bin/sh "$studio_directory/START.sh" "$@"
