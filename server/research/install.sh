#!/usr/bin/env bash
# Root on eloquent-rosalind. Does not enable the timer until GitHub has a
# protected main branch and a read-only deploy key installed.
set -euo pipefail
umask 077
if [[ "$EUID" -ne 0 ]]; then
 echo "Run via sudo on your approved host." >&2; exit 1
fi
for executable in python3 git docker systemctl; do
 command -v "$executable" >/dev/null || { echo "Missing $executable" >&2; exit 1; }
done
src="$(cd "$(dirname "$0")" && pwd)"
install -d -m 0700 /opt/expert-robot/worker /etc/expert-robot-github /opt/expert-robot/git /var/lib/expert-robot/research
install -m 0700 "$src/worker.py" /opt/expert-robot/worker/worker.py
install -m 0644 "$src/expert-robot-research.service" /etc/systemd/system/expert-robot-research.service
install -m 0644 "$src/expert-robot-research.timer" /etc/systemd/system/expert-robot-research.timer
if [[ ! -f /etc/expert-robot-github/worker.env ]]; then
cat > /etc/expert-robot-github/worker.env.example <<'EOF'
# DO NOT PUT PRIVATE KEY MATERIAL IN THIS FILE.
# Configure a GitHub read-only deploy key and pin the verified GitHub SSH host key.
GIT_SSH_COMMAND="/usr/bin/ssh -i /etc/expert-robot-github/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/etc/expert-robot-github/known_hosts"
EOF
chmod 0600 /etc/expert-robot-github/worker.env.example
fi
systemctl daemon-reload
echo "Plesk server research service and timer installed but NOT activated."
echo "Complete /etc/expert-robot-github/worker.env and a GitHub read-only deployment key."
echo "Protect the intended GitHub branch and configure the read-only deploy key."
echo "Clone once at /opt/expert-robot/git/expert-robot from git@github.com:Mannyspiro/expert-robot.git."
echo "Configure WORKER_IMAGE=docker.io/library/python@sha256:<verified_digest> in worker.env."
echo "Then test: sudo systemctl start expert-robot-research.service"
echo "Inspect: sudo journalctl -u expert-robot-research.service --no-pager -n 100"
echo "Only after successful sandbox+evidence verification: sudo systemctl enable --now expert-robot-research.timer"
