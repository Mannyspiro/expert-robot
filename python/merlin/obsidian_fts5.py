"""Optional memory-only SQLite FTS5 search over an explicit Obsidian vault.

No note writes, on-disk index, remote model, new durable memory or graph edits.
Vault text is untrusted content, not an instruction or verified factual claim.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import sqlite3

from .obsidian_vault_bridge import ObsidianVaultBridge, WORD

MAX_FTS_SOURCE_BYTES = 8 * 1024 * 1024
MAX_TERMS = 8


def local_fts5_search(vault: ObsidianVaultBridge, query: str, *, limit: int = 10,
                      include_snippets: bool = False) -> dict:
    """Build a bounded transient FTS5 index and return hash-bound note IDs."""
    if not isinstance(vault, ObsidianVaultBridge):
        raise TypeError('an explicit ObsidianVaultBridge is required')
    if not isinstance(query, str) or not query.strip() or len(query) > 160:
        raise ValueError('bounded search query required')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('limit must be between 1 and 100')
    terms = [term.casefold() for term in WORD.findall(query)]
    if not terms:
        return {'schema': 'merlin-obsidian-fts5/1', 'query': query, 'results': [],
                'persistent_memory_changed': False, 'production_qualified': False}
    if len(terms) > MAX_TERMS:
        raise ValueError('query has too many terms')
    # Every token is a quoted literal, not FTS5 syntax/commands.
    expression = ' AND '.join('"' + t.replace('"', '""') + '"' for t in terms)
    snapshot = vault.read()
    if snapshot['source_bytes_scanned'] > MAX_FTS_SOURCE_BYTES:
        raise ValueError('vault exceeds opt-in in-memory index source budget')
    used = 0
    records = []
    for note in snapshot['notes']:
        raw = vault._read(note['path'])
        if hashlib.sha256(raw).hexdigest() != note['sha256']:
            raise RuntimeError('vault note changed between inventory and FTS indexing')
        used += len(raw)
        if used > MAX_FTS_SOURCE_BYTES:
            raise ValueError('vault exceeds in-memory FTS read budget')
        records.append((note['path'], note['sha256'], note['title'],
                        ' '.join(note['tags']), ' '.join(note['aliases']),
                        raw.decode('utf-8')))
    try:
        with closing(sqlite3.connect(':memory:')) as db:
            db.execute('PRAGMA temp_store=MEMORY')
            db.execute("""CREATE VIRTUAL TABLE notes USING fts5(
                path UNINDEXED, sha256 UNINDEXED, title, tags, aliases, body,
                tokenize='unicode61 remove_diacritics 2')""")
            db.executemany('INSERT INTO notes(path,sha256,title,tags,aliases,body) VALUES(?,?,?,?,?,?)', records)
            rows = db.execute('SELECT path,sha256 FROM notes WHERE notes MATCH ? '
                              'ORDER BY bm25(notes, 0.0, 0.0, 5.0, 2.0, 2.0, 1.0), path LIMIT ?',
                              (expression, limit)).fetchall()
    except sqlite3.OperationalError as exc:
        raise RuntimeError('SQLite FTS5 unavailable or rejected bounded query') from exc
    results = []
    for path, digest in rows:
        raw = vault._read(path)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise RuntimeError('vault note changed between FTS search and evidence readback')
        entry = {'path': path, 'sha256': digest}
        if include_snippets:
            lines = raw.decode('utf-8').splitlines()
            line = next((i for i, text in enumerate(lines, 1)
                         if all(term in text.casefold() for term in terms)), None)
            entry['line'] = line
            if line:
                entry['snippet'] = lines[line - 1][:200]
        results.append(entry)
    return {'schema': 'merlin-obsidian-fts5/1', 'query': query, 'results': results,
            'index': 'SQLite FTS5 memory-only', 'status': snapshot['status'],
            'omissions': snapshot['omissions'], 'source_bytes_indexed': used,
            'source_content_emitted': bool(include_snippets),
            'persistent_memory_changed': False, 'production_qualified': False}
