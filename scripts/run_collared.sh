#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_collared.sh --sealed <core.enc> --key-file <generation.key> \
    --image <image@sha256:digest> --workspace <dir> -- <command> [args...]

Requirements:
- Linux host inside a dedicated hardware-virtualized guest
- Docker, findmnt, timeout, sha256sum, readlink and systemd-detect-virt
- /dev/shm is tmpfs
- generation key is freshly provisioned by the external orchestrator on /dev/shm
- no user passkey

The generation key is one-use and is destroyed on success, failure, or trip.
The sandbox never receives repository credentials, host sockets, or promotion authority.
EOF
}

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 2
  }
}

SEALED=""
KEY=""
IMAGE=""
WORKSPACE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --sealed) SEALED="$2"; shift 2 ;;
    --key-file) KEY="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --) shift; break ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$SEALED" ] && [ -n "$KEY" ] && [ -n "$IMAGE" ] && [ -n "$WORKSPACE" ] && [ "$#" -gt 0 ] || {
  usage
  exit 2
}

for cmd in docker findmnt timeout sha256sum readlink systemd-detect-virt python3; do
  require "$cmd"
done

case "$IMAGE" in
  *@sha256:[0-9a-f][0-9a-f]*) ;;
  *)
    echo "container image must be pinned by sha256 digest" >&2
    exit 43
    ;;
esac

virt="$(systemd-detect-virt 2>/dev/null || true)"
case "$virt" in
  kvm|qemu|xen|microsoft|vmware|oracle|amazon|google|parallels)
    ;;
  *)
    echo "collar requires a hardware-virtualized guest; detected: ${virt:-none}" >&2
    exit 43
    ;;
esac

SEALED="$(readlink -f "$SEALED")"
KEY="$(readlink -f "$KEY")"
WORKSPACE="$(readlink -f "$WORKSPACE")"

test -f "$SEALED"
test -f "${SEALED}.hmac"
test -f "$KEY"

case "$KEY" in
  /dev/shm/*) ;;
  *)
    echo "generation key must live on /dev/shm tmpfs" >&2
    exit 42
    ;;
esac

case "$SEALED" in
  "$WORKSPACE"|"$WORKSPACE"/*)
    echo "sealed core must remain outside candidate-writable workspace" >&2
    exit 42
    ;;
esac
case "$KEY" in
  "$WORKSPACE"|"$WORKSPACE"/*)
    echo "generation key must remain outside candidate-writable workspace" >&2
    exit 42
    ;;
esac

ROOT="/dev/shm/expert-robot-collar-$RANDOM-$$"
PLAIN="$ROOT/core"
CANARY="$ROOT/supervisor.canary"
EVIDENCE="$WORKSPACE/collar-evidence"
NAME="expert-robot-collared-$RANDOM-$$"
TRIPPED=0
TRIP_REASON=""
EXIT_CODE=125

mkdir -p "$ROOT" "$PLAIN" "$WORKSPACE"
chmod 700 "$ROOT" "$PLAIN" "$WORKSPACE"

fstype="$(findmnt -T "$ROOT" -n -o FSTYPE || true)"
[ "$fstype" = "tmpfs" ] || {
  echo "collar plaintext root must be tmpfs, got: $fstype" >&2
  rm -rf "$ROOT"
  exit 42
}
key_fstype="$(findmnt -T "$KEY" -n -o FSTYPE || true)"
[ "$key_fstype" = "tmpfs" ] || {
  echo "generation key must be on tmpfs, got: $key_fstype" >&2
  rm -rf "$ROOT"
  exit 42
}

printf '%s\n' "$RANDOM-$RANDOM-$$" > "$CANARY"
chmod 600 "$CANARY"
CANARY_HASH="$(sha256sum "$CANARY" | awk '{print $1}')"

cleanup() {
  set +e
  docker kill "$NAME" >/dev/null 2>&1
  docker rm -f "$NAME" >/dev/null 2>&1
  scripts/collar_vault.sh destroy-key "$KEY" >/dev/null 2>&1
  rm -rf "$PLAIN" "$ROOT"
}
trap cleanup EXIT INT TERM

scripts/collar_vault.sh unseal "$KEY" "$SEALED" "$PLAIN"

trip() {
  TRIPPED=1
  TRIP_REASON="$1"
  docker kill "$NAME" >/dev/null 2>&1 || true
}

docker run -d \
  --name "$NAME" \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --pids-limit 128 \
  --memory 8g \
  --cpus 8 \
  --user 65532:65532 \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=512m \
  --tmpfs /run/expert-robot:rw,noexec,nosuid,nodev,size=64m \
  --mount "type=bind,src=$PLAIN,dst=/opt/expert-robot/core,readonly" \
  --mount "type=bind,src=$WORKSPACE,dst=/work" \
  --workdir /work \
  "$IMAGE" "$@" >/dev/null

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

while true; do
  if ! inspect="$(timeout 5s docker inspect "$NAME" 2>/dev/null)"; then
    trip "supervisor_heartbeat_missing"
    break
  fi

  if [ "$(sha256sum "$CANARY" | awk '{print $1}')" != "$CANARY_HASH" ]; then
    trip "supervisor_canary_tamper"
    break
  fi

  running="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)[0]["State"]["Running"]).lower())')"
  privileged="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)[0]["HostConfig"]["Privileged"]).lower())')"
  readonly="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)[0]["HostConfig"]["ReadonlyRootfs"]).lower())')"
  network="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["HostConfig"]["NetworkMode"])')"
  capdrop="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)[0]["HostConfig"].get("CapDrop") or []))')"
  security="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)[0]["HostConfig"].get("SecurityOpt") or []))')"
  user="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["Config"].get("User") or "")')"
  pids="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["HostConfig"].get("PidsLimit") or 0)')"
  memory="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["HostConfig"].get("Memory") or 0)')"
  nanocpus="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["HostConfig"].get("NanoCpus") or 0)')"
  mounts="$(printf '%s' "$inspect" | python3 -c 'import json,sys; m=json.load(sys.stdin)[0].get("Mounts") or []; print("|".join(sorted(f"{x.get(\"Type\")}:{x.get(\"Destination\")}:{str(bool(x.get(\"RW\"))).lower()}" for x in m)))')"

  if [ "$privileged" != "false" ]; then trip "privileged_drift"; break; fi
  if [ "$readonly" != "true" ]; then trip "readonly_root_drift"; break; fi
  if [ "$network" != "none" ]; then trip "network_namespace_changed"; break; fi
  case ",$capdrop," in *,ALL,*) ;; *) trip "capability_drop_drift"; break ;; esac
  case "$security" in *no-new-privileges*) ;; *) trip "no_new_privileges_drift"; break ;; esac
  if [ "$user" != "65532:65532" ]; then trip "runtime_user_drift"; break; fi
  if [ "$pids" -ne 128 ]; then trip "process_limit_drift"; break; fi
  if [ "$memory" -ne 8589934592 ]; then trip "memory_limit_drift"; break; fi
  if [ "$nanocpus" -ne 8000000000 ]; then trip "cpu_limit_drift"; break; fi
  if [ "$mounts" != "bind:/opt/expert-robot/core:false|bind:/work:true" ]; then
    trip "unexpected_host_mount"
    break
  fi

  if [ "$running" != "true" ]; then
    EXIT_CODE="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["State"]["ExitCode"])')"
    break
  fi

  sleep 2
done

ended="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Candidate had write access to the workspace, so replace the evidence directory
# only after the container has stopped. This prevents symlink/file substitution.
rm -rf -- "$EVIDENCE"
mkdir -p "$EVIDENCE"
chmod 700 "$EVIDENCE"

python3 - "$started" "$ended" "$IMAGE" "$virt" "$TRIPPED" "$TRIP_REASON" "$EXIT_CODE" > "$EVIDENCE/result.json" <<'PY'
import json
import sys
started, ended, image, virtualization, tripped, reason, exit_code = sys.argv[1:]
print(json.dumps({
    "schema_version": 2,
    "collar": "fail-closed-collar-v1",
    "started": started,
    "ended": ended,
    "image": image,
    "image_digest_pinned": True,
    "virtualization": virtualization,
    "tripped": tripped == "1",
    "trip_reason": reason,
    "exit_code": int(exit_code),
    "promotion_authority": False,
    "external_policy_may_promote_after_all_gates": True,
    "plaintext_persisted": False,
    "generation_key_persisted": False,
}, indent=2))
PY
chmod 600 "$EVIDENCE/result.json"

if [ "$TRIPPED" -eq 1 ]; then
  echo "COLLAR_TRIPPED: $TRIP_REASON" >&2
  exit 70
fi

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "generation exited non-zero: $EXIT_CODE" >&2
  exit "$EXIT_CODE"
fi

echo "collared generation completed; promotion authority remains outside the sandbox"
