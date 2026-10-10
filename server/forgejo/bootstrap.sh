#!/usr/bin/env bash
# Run via sudo on eloquent-rosalind.66-179-137-120.plesk.page, after SSH verification.
# Does not open cloud firewall ports or import private repositories.
set -euo pipefail
umask 077
if [[ "$EUID" -ne 0 ]]; then
  echo "Run with sudo on the designated Plesk server" >&2
  exit 1
fi
command -v docker >/dev/null || { echo "Docker Engine missing; install from distribution packages" >&2; exit 1; }
docker compose version >/dev/null || { echo "Docker Compose plugin missing" >&2; exit 1; }
arch="$(uname -m)"
[[ "$arch" = x86_64 || "$arch" = aarch64 ]] || { echo "Unsupported architecture" >&2; exit 1; }
src="$(cd "$(dirname "$0")" && pwd)"
dest="/opt/expert-robot/forgejo"
if [[ -L "$dest" ]]; then echo "Refusing symlinked install path" >&2; exit 1; fi
install -d -m 0700 "$dest"
install -d -m 0700 "$dest/data" "$dest/config"
chown 10001:10001 "$dest/data" "$dest/config"
if [[ -f "$dest/compose.yaml" ]] && ! cmp -s "$src/compose.yaml" "$dest/compose.yaml"; then
  echo "Existing composition differs: back up and review before upgrade" >&2; exit 1
fi
install -m 0600 "$src/compose.yaml" "$dest/compose.yaml"
if [[ ! -f "$dest/.env" ]]; then
  tag="codeberg.org/forgejo/forgejo:16-rootless"
  docker pull "$tag"
  digest="$(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "$tag" |
    grep -E '^codeberg.org/forgejo/forgejo@sha256:[0-9a-f]{64}
(
  cd "$dest"
  docker compose --env-file .env config --quiet
  docker compose --env-file .env up -d
)
echo "Private Forgejo started on Plesk server loopback only."
echo "Leave Plesk ports 80/443 and firewall rules unchanged; do not expose ports 3000/2222."
echo "From your workstation: ssh -L 3000:127.0.0.1:3000 -L 2222:127.0.0.1:2222 <admin>@eloquent-rosalind.66-179-137-120.plesk.page"
echo "Open http://127.0.0.1:3000/ through the tunnel and complete administrator setup."
echo "Require MFA and verified encrypted backups before using this as sole source of truth."
 | head -n 1)"
  [[ "$digest" =~ ^codeberg.org/forgejo/forgejo@sha256:[0-9a-f]{64}$ ]] ||
    { echo "Image digest pin missing" >&2; exit 1; }
  printf 'FORGEJO_IMAGE=%s\n' "$digest" > "$dest/.env"
  chmod 0600 "$dest/.env"
fi
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
