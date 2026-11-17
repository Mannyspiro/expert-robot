"""Operator CLI. Import and handoff writes are separate from the read-only MCP."""
import argparse
import json
from pathlib import Path

from merlin.project_registry import MerlinRegistry
from .bridge import DotContextBridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    ingest = sub.add_parser("ingest")
    ingest.add_argument("manifest", type=Path)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--namespace")
    search.add_argument("--budget-bytes", type=int, default=14000)
    sub.add_parser("status")
    args = parser.parse_args()
    bridge = DotContextBridge(MerlinRegistry(args.root))
    if args.command == "init":
        bridge.initialize()
        result = bridge.status()
    elif args.command == "ingest":
        manifest = json.loads(args.manifest.read_text("utf-8"))
        if not isinstance(manifest, list) or not 1 <= len(manifest) <= 800:
            raise ValueError("manifest must be an explicit source list of at most 800 records")
        result = []
        for item in manifest:
            item = dict(item)
            file = args.manifest.parent / item.pop("local_path")
            with file.open("rb") as stream:
                content = stream.read(4 * 1024 * 1024 + 1)
            result.append(bridge.ingest(content=content, **item))
    elif args.command == "search":
        result = bridge.search(args.query, namespace=args.namespace, budget_bytes=args.budget_bytes)
    else:
        result = bridge.status()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
