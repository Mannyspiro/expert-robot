#!/usr/bin/env bash
# Root on cace-oci-a1. Does not enable the timer until Forgejo has a
# protected main branch and a read-only deploy key installed.
set -euo pipefail
umask 077
if [[ "$EUID" -ne 0 ]]; then
 echo "Run via sudo on your OCI host." >&2; exit 1
fi
for executable in python3 git docker systemctl; do
 command -v "$executable" >/dev/null || { echo "Missing $executable" >&2; exit 1; }
done
src="$(cd "$(dirname "$0")" && pwd)"
install -d -m 0700 /opt/oci-research /etc/oci-research /srv/oci-research /var/lib/oci-research
install -m 0700 "$src/worker.py" /opt/oci-research/worker.py
install -m 0644 "$src/oci-research.service" /etc/systemd/system/oci-research.service
install -m 0644 "$src/oci-research.timer" /etc/systemd/system/oci-research.timer
if [[ ! -f /etc/oci-research/worker.env ]]; then
cat > /etc/oci-research/worker.env.example <<'EOF'
# DO NOT PUT PRIVATE KEY MATERIAL IN THIS FILE.
# Generate an OCI-only read-only deploy key and verify Forgejo host key first.
GIT_SSH_COMMAND="/usr/bin/ssh -i /etc/oci-research/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/etc/oci-research/known_hosts"
EOF
chmod 0600 /etc/oci-research/worker.env.example
fi
systemctl daemon-reload
echo "OCI research service and timer installed but NOT activated."
echo "Complete /etc/oci-research/worker.env and the read-only Forgejo deployment key."
echo "Import/migrate the existing repository and protect its default main branch."
echo "Clone once at /srv/oci-research/expert-robot from ssh://git@127.0.0.1:2222/Mannyspiro/expert-robot.git."
echo "Then test: sudo systemctl start oci-research.service"
echo "Inspect: sudo journalctl -u oci-research.service --no-pager -n 100"
echo "Only after successful sandbox+evidence verification: sudo systemctl enable --now oci-research.timer"
