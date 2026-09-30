#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  run_collared.sh --sealed <core.enc> --image <image> --workspace <dir> -- <command> [args...]

Requirements:
- Linux host inside a dedicated VM/hardware-virtualized guest
- Docker available
- /dev/shm available as tmpfs
- no user passkey; an ephemeral key is generated per run

The sandbox is fail-closed. It never grants promotion authority.
EOF
}

SEALED=""
IMAGE=""
WORKSPACE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --sealed) SEALED="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --workspace) WORKSPACE="$2"; shift 2 ;;
    --) shift; break ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$SEALED" ] && [ -n "$IMAGE" ] && [ -n "$WORKSPACE" ] && [ "$#" -gt 0 ] || {
  usage
  exit 2
}

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required for collar v1" >&2
  exit 2
}
command -v findmnt >/dev/null 2>&1 || {
  echo "findmnt is required for collar v1" >&2
  exit 2
}

ROOT="/dev/shm/expert-robot-collar-$RANDOM-$$"
KEY="$ROOT/generation.key"
PLAIN="$ROOT/core"
EVIDENCE="$WORKSPACE/collar-evidence"
NAME="expert-robot-collared-$RANDOM-$$"
TRIPPED=0
TRIP_REASON=""
EXIT_CODE=125

mkdir -p "$ROOT" "$PLAIN" "$WORKSPACE" "$EVIDENCE"
chmod 700 "$ROOT" "$PLAIN" "$WORKSPACE" "$EVIDENCE"

fstype="$(findmnt -T "$ROOT" -n -o FSTYPE || true)"
[ "$fstype" = "tmpfs" ] || {
  echo "collar plaintext/key root must be tmpfs, got: $fstype" >&2
  rm -rf "$ROOT"
  exit 42
}

cleanup() {
  set +e
  docker kill "$NAME" >/dev/null 2>&1
  docker rm -f "$NAME" >/dev/null 2>&1
  scripts/collar_vault.sh destroy-key "$KEY" >/dev/null 2>&1
  rm -rf "$PLAIN" "$ROOT"
}
trap cleanup EXIT INT TERM

scripts/collar_vault.sh keygen "$KEY"
scripts/collar_vault.sh unseal "$KEY" "$SEALED" "$PLAIN"

trip() {
  TRIPPED=1
  TRIP_REASON="$1"
  docker kill "$NAME" >/dev/null 2>&1 || true
}

docker run -d   --name "$NAME"   --network none   --read-only   --cap-drop ALL   --security-opt no-new-privileges:true   --pids-limit 128   --memory 8g   --cpus 8   --user 65532:65532   --tmpfs /tmp:rw,noexec,nosuid,nodev,size=512m   --tmpfs /run/expert-robot:rw,noexec,nosuid,nodev,size=64m   --mount "type=bind,src=$PLAIN,dst=/opt/expert-robot/core,readonly"   --mount "type=bind,src=$WORKSPACE,dst=/work"   --workdir /work   "$IMAGE" "$@" >/dev/null

started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
last_inspect="$(date +%s)"

while true; do
  inspect="$(docker inspect "$NAME" 2>/dev/null)" || {
    trip "docker_inspect_failed"
    break
  }

  running="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)[0]["State"]["Running"]).lower())')"
  privileged="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)[0]["HostConfig"]["Privileged"]).lower())')"
  readonly="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)[0]["HostConfig"]["ReadonlyRootfs"]).lower())')"
  network="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["HostConfig"]["NetworkMode"])')"
  capdrop="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)[0]["HostConfig"].get("CapDrop") or []))')"
  security="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)[0]["HostConfig"].get("SecurityOpt") or []))')"

  if [ "$privileged" != "false" ]; then trip "privileged_drift"; break; fi
  if [ "$readonly" != "true" ]; then trip "readonly_root_drift"; break; fi
  if [ "$network" != "none" ]; then trip "network_namespace_changed"; break; fi
  case ",$capdrop," in *,ALL,*) ;; *) trip "capability_drop_drift"; break ;; esac
  case "$security" in *no-new-privileges*) ;; *) trip "no_new_privileges_drift"; break ;; esac

  if [ "$running" != "true" ]; then
    EXIT_CODE="$(printf '%s' "$inspect" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["State"]["ExitCode"])')"
    break
  fi

  now="$(date +%s)"
  if [ $((now - last_inspect)) -gt 15 ]; then
    trip "supervisor_heartbeat_missing"
    break
  fi
  last_inspect="$now"
  sleep 2
done

ended="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
cat > "$EVIDENCE/result.json" <<EOF
{
  "schema_version": 1,
  "collar": "fail-closed-collar-v1",
  "started": "$started",
  "ended": "$ended",
  "image": "$IMAGE",
  "tripped": $([ "$TRIPPED" -eq 1 ] && echo true || echo false),
  "trip_reason": "$TRIP_REASON",
  "exit_code": $EXIT_CODE,
  "promotion_authority": false,
  "plaintext_persisted": false,
  "key_persisted": false
}
EOF

if [ "$TRIPPED" -eq 1 ]; then
  echo "COLLAR_TRIPPED: $TRIP_REASON" >&2
  exit 70
fi

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "generation exited non-zero: $EXIT_CODE" >&2
  exit "$EXIT_CODE"
fi

echo "collared generation completed without trip; promotion remains disabled"
