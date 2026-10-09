#!/usr/bin/env bash
# Root on eloquent-rosalind. Does not enable the timer until Forgejo has a
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
install -d -m 0700 /opt/expert-robot/worker /etc/expert-robot-forge /opt/expert-robot/git /var/lib/expert-robot/research
install -m 0700 "$src/worker.py" /opt/expert-robot/worker/worker.py
install -m 0644 "$src/expert-robot-research.service" /etc/systemd/system/expert-robot-research.service
install -m 0644 "$src/expert-robot-research.timer" /etc/systemd/system/expert-robot-research.timer
if [[ ! -f /etc/expert-robot-forge/worker.env ]]; then
cat > /etc/expert-robot-forge/worker.env.example <<'EOF'
# DO NOT PUT PRIVATE KEY MATERIAL IN THIS FILE.
# Generate an Plesk-server-only read-only deploy key and verify Forgejo host key first.
GIT_SSH_COMMAND="/usr/bin/ssh -i /etc/expert-robot-forge/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/etc/expert-robot-forge/known_hosts"
EOF
chmod 0600 /etc/expert-robot-forge/worker.env.example
fi
systemctl daemon-reload
echo "Plesk server research service and timer installed but NOT activated."
echo "Complete /etc/expert-robot-forge/worker.env and the read-only Forgejo deployment key."
echo "Import/migrate the existing repository and protect its default main branch."
echo "Clone once at /opt/expert-robot/git/expert-robot from ssh://git@127.0.0.1:2222/Mannyspiro/expert-robot.git."
echo "Then test: sudo systemctl start expert-robot-research.service"
echo "Inspect: sudo journalctl -u expert-robot-research.service --no-pager -n 100"
echo "Only after successful sandbox+evidence verification: sudo systemctl enable --now expert-robot-research.timer"
