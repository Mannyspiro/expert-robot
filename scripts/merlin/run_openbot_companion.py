#!/usr/bin/env python3
"""Launch pinned MIT OpenBot as a separate local Merlin companion.

It is never launched automatically by Merlin. It has separate state, tools,
and approvals and cannot confer privileges to the Merlin process.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess


def plan(repo_root, *, model_port=8772, bot_port=4178, data_dir=None):
    root = Path(repo_root).resolve()
    source = root / "third_party" / "openbot"
    if not (source / "server.mjs").is_file() or not (source / "LICENSE").is_file():
        raise ValueError("fetch pinned OpenBot source first: git submodule update --init third_party/openbot")
    if type(model_port) is not int or type(bot_port) is not int or not all(1024 <= n <= 65535 for n in (model_port, bot_port)):
        raise ValueError("invalid local port")
    if model_port == bot_port:
        raise ValueError("model and OpenBot ports must differ")
    state = Path(data_dir).expanduser().resolve() if data_dir else (root / ".local-merlin" / "openbot").resolve()
    env = os.environ.copy()
    # Fail closed regardless of inherited OpenBot remote or browser settings.
    env.update({"HOST": "127.0.0.1", "PORT": str(bot_port),
                "OPENBOT_MODEL_URL": "http://127.0.0.1:" + str(model_port),
                "OPENBOT_MODEL_PROTOCOL": "chat-completions", "OPENBOT_LOCAL_ONLY": "1",
                "OPENBOT_REMOTE_BASE_URL": "", "OPENBOT_REMOTE_API_KEY": "",
                "OPENBOT_BROWSER_ALLOW_HOSTS": "127.0.0.1,localhost",
                "OPENBOT_DATA_DIR": str(state), "OPENBOT_RESOURCE_PROFILE": "legacy"})
    return ["node", str(source / "server.mjs")], str(source), env


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run pinned OpenBot without changing Merlin authority")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--model-port", type=int, default=8772)
    parser.add_argument("--port", type=int, default=4178)
    parser.add_argument("--data-dir")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        cmd, cwd, env = plan(args.repo, model_port=args.model_port, bot_port=args.port, data_dir=args.data_dir)
    except ValueError as error:
        parser.error(str(error))
    if args.dry_run:
        print(json.dumps({"command": cmd, "cwd": cwd, "port": args.port,
                          "model_endpoint": env["OPENBOT_MODEL_URL"], "data_dir": env["OPENBOT_DATA_DIR"],
                          "local_only": env["OPENBOT_LOCAL_ONLY"]}, sort_keys=True))
        return 0
    Path(env["OPENBOT_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    print("OpenBot dashboard: http://127.0.0.1:%d" % args.port, flush=True)
    try:
        return subprocess.call(cmd, cwd=cwd, env=env)
    except FileNotFoundError:
        parser.error("Node.js 20+ is required; install it separately")


if __name__ == "__main__":
    raise SystemExit(main())
