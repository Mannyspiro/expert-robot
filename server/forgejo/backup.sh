#!/usr/bin/env bash
# Offline consistent local backup: briefly stops Forgejo to include SQLite safely.
# Keep a second encrypted off-host backup before moving primary development.
set -euo pipefail
umask 077
if [[ "$EUID" -ne 0 ]]; then echo "Run via sudo on the designated Plesk server" >&2; exit 1; fi
root=/opt/expert-robot/forgejo
[[ -f "$root/compose.yaml" && -d "$root/data" ]] || { echo "Forgejo not installed" >&2; exit 1; }
command -v docker >/dev/null
command -v tar >/dev/null
dir=/var/backups/oci-forgejo
install -d -m 0700 "$dir"
archive="$dir/forgejo-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
cd "$root"
docker compose stop
restart() { docker compose up -d || echo "WARNING: Forgejo restart failed" >&2; }
trap restart EXIT
tar -czf "$archive" --numeric-owner compose.yaml data config
chmod 0600 "$archive"
sha256sum "$archive" > "$archive.sha256"
chmod 0600 "$archive.sha256"
echo "Consistent local compressed backup: $archive"
echo "This backup contains private repositories and credentials; encrypt before off-host transfer."
