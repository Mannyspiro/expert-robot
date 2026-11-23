#!/usr/bin/env python3
"""Explicit read-only Obsidian vault inspector; user supplies local vault root."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from merlin.obsidian_vault_bridge import ObsidianVaultBridge
from merlin.obsidian_fts5 import local_fts5_search


def main() -> int:
    p = argparse.ArgumentParser(description='Inspect an Obsidian-compatible Markdown vault without changing it')
    p.add_argument('--vault', type=Path, required=True, help='explicit local vault root')
    p.add_argument('--search', help='optional local vault search')
    p.add_argument('--mode', choices=('lexical', 'fts5'), default='lexical', help='explicit search engine; FTS5 is memory-only')
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--include-snippets', action='store_true', help='explicitly allow displaying selected private note lines')
    args = p.parse_args()
    if args.include_snippets and not args.search:
        p.error('snippets require --search')
    if args.mode == 'fts5' and not args.search:
        p.error('FTS5 mode requires --search')
    bridge = ObsidianVaultBridge(args.vault)
    if args.search:
        result = (local_fts5_search(bridge, args.search, limit=args.limit, include_snippets=args.include_snippets)
                  if args.mode == 'fts5' else
                  bridge.search(args.search, limit=args.limit, include_snippets=args.include_snippets))
    else:
        result = bridge.read()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result.get('status') == 'partial' else 0


if __name__ == '__main__':
    raise SystemExit(main())
