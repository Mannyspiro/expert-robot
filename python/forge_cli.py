#!/usr/bin/env python3
"""Command-line interface for Merlin's local Virtual Forge."""
from __future__ import annotations

import argparse
import json
import sys

from virtual_forge import ForgeError, VirtualForge


def main() -> int:
    parser = argparse.ArgumentParser(description="Merlin Virtual GitHub Forge")
    parser.add_argument("--db", default=".merlin/forge.sqlite3", help="SQLite Forge database")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("status")
    branch = commands.add_parser("branch")
    branch.add_argument("name")
    branch.add_argument("--from-branch", default="main")
    commit = commands.add_parser("commit")
    commit.add_argument("branch")
    commit.add_argument("message")
    commit.add_argument("--author", default="merlin")
    commit.add_argument("--expected-head")
    commit.add_argument("--file", action="append", required=True, metavar="PATH=FILE")
    pr = commands.add_parser("pr")
    pr.add_argument("source")
    pr.add_argument("--target", default="main")
    pr.add_argument("--title", default="Merlin change")
    merge = commands.add_parser("merge")
    merge.add_argument("pr_id")
    merge.add_argument("--author", default="merlin")
    export = commands.add_parser("export")
    export.add_argument("branch")
    export.add_argument("destination")
    args = parser.parse_args()

    forge = VirtualForge(args.db)
    try:
        if args.command == "status":
            print(json.dumps({
                "branches": forge.branches(),
                "pull_requests": forge.pull_requests(),
                "event_chain_valid": forge.verify_event_chain(),
            }, indent=2))
        elif args.command == "branch":
            print(forge.create_branch(args.name, args.from_branch))
        elif args.command == "commit":
            changes = {}
            for item in args.file:
                if "=" not in item:
                    raise ForgeError("--file must be PATH=FILE")
                path, source = item.split("=", 1)
                with open(source, encoding="utf-8") as handle:
                    changes[path] = handle.read()
            print(forge.commit(args.branch, changes, args.message, args.author, args.expected_head))
        elif args.command == "pr":
            print(forge.open_pull_request(args.source, args.target, args.title))
        elif args.command == "merge":
            print(forge.merge_pull_request(args.pr_id, args.author))
        elif args.command == "export":
            print(json.dumps({"files": forge.export_snapshot(args.branch, args.destination)}))
        return 0
    except ForgeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    finally:
        forge.close()


if __name__ == "__main__":
    raise SystemExit(main())
