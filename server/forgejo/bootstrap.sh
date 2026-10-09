#!/usr/bin/env bash
# On the designated Plesk server itself: sudo bash ./oci/forgejo/bootstrap.sh
# Does not open cloud firewall ports or import private repositories.
set -euo pipefail
umask 077
if [[ "$EUID" -ne 0 ]]; then
  echo "Run with sudo on the authorized OCI ARM64 host" >&2
  exit 1
fi
command -v docker >/dev/null || { echo "Docker Engine missing; install from distribution packages" >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose plugin missing" >&2; exit 1; }
src="$(cd "$(dirname "$0")" && pwd)"
dest="/opt/expert-robot/forgejo"
if [[ -L "$dest" ]]; then echo "Refusing symlinked install path" >&2; exit 1; fi
install -d -m 0700 "$dest"
install -d -m 0700 "$dest/data" "$dest/config"
chown 10001:10001 "$dest/data" "$dest/config"
install -m 0600 "$src/compose.yaml" "$dest/compose.yaml"
(
  cd "$dest"
  docker compose config --quiet
  docker compose pull
  docker compose up -d
)
echo "Private Forgejo service started; ports are bound to OCI loopback only."
echo "Check OCI's ingress rules: do not expose TCP 3000/2222 on public networks."
echo "From your workstation: ssh -L 3000:127.0.0.1:3000 -L 2222:127.0.0.1:2222 <oci-login>@<oci-host>"
echo "Open http://127.0.0.1:3000/ through the tunnel and complete administrator setup."
echo "Require MFA and verified encrypted backups before using this as sole source of truth."
