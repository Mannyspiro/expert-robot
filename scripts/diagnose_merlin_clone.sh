#!/usr/bin/env bash
# Safe private-repository checkout diagnostics. Does not modify DNS, credentials, or billing.
set -u
repo="${1:-Mannyspiro/expert-robot}"
branch="${2:-merlin/release-gate-evidence-20261121}"
printf 'git=%s\n' "$(git --version)"
printf 'dns='
getent ahostsv4 github.com | head -n 1 || true
printf 'proxy_variables='
env | cut -d= -f1 | grep -i proxy | sort | tr '\n' ' ' || true
echo
printf 'https_status='
curl -sSI --max-time 8 https://github.com -o /dev/null -w '%{http_code}\n' 2>/dev/null || echo unreachable
printf 'git_remote='
timeout 10 git ls-remote "https://github.com/${repo}.git" "refs/heads/${branch}" 2>&1 | sed -E 's#(https?://)[^/@ ]+@#\1[redacted]@#g' | head -n 3 || true
echo 'If DNS fails here, run the checkout on a host with authorized network access.'
echo 'For a private repository, use authenticated gh repo clone or credential-managed git; never put tokens in URLs.'
