#!/usr/bin/env python3
"""Explicit read-only Obsidian vault inspector; user supplies local vault root."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from merlin.obsidian_vault_bridge import ObsidianVaultBridge


def main() -> int:
    p = argparse.ArgumentParser(description='Inspect an Obsidian-compatible Markdown vault without changing it')
    p.add_argument('--vault', type=Path, required=True, help='explicit local vault root')
    p.add_argument('--search', help='optional lexical search')
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--include-snippets', action='store_true', help='explicitly allow displaying selected private note lines')
    args = p.parse_args()
    if args.include_snippets and not args.search:
        p.error('snippets require --search')
    bridge = ObsidianVaultBridge(args.vault)
    result = bridge.search(args.search, limit=args.limit, include_snippets=args.include_snippets) if args.search else bridge.read()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result.get('status') == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
