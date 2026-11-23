"""Opt-in read-only Obsidian Markdown vault bridge for Merlin.

Untrusted local notes are never automatically promoted to memory, an artifact
registry, a model prompt, the network or a production approval.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import unquote

MAX_NOTES = 2000
MAX_NOTE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
IGNORE = frozenset({'.obsidian', '.git', '.trash', '.merlin', 'node_modules', '__pycache__'})
WIKI = re.compile(r'!?(?<!\[)\[\[([^\[\]\n]{1,240})\]\]')
MARKDOWN = re.compile(r'(?<!!)\[[^\]\n]{1,200}\]\(([^)\n]{1,500})\)')
TAG = re.compile(r'(?<![\w#])#([\w/-]{1,60})', re.UNICODE)
WORD = re.compile(r'[\w-]+', re.UNICODE)


@dataclass(frozen=True)
class Link:
    target: str
    line: int
    style: str


@dataclass(frozen=True)
class Note:
    path: str
    title: str
    sha256: str
    tags: tuple[str, ...]
    aliases: tuple[str, ...]
    links: tuple[Link, ...]


def _safe_relative(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or '\\' in value or '\x00' in value:
        raise ValueError('unsafe note path')
    path = PurePosixPath(value)
    if path.is_absolute() or any(x in ('', '.', '..') or x.startswith('.') for x in value.split('/')):
        raise ValueError('unsafe note path')
    if not value.lower().endswith('.md'):
        raise ValueError('only Markdown notes permitted')
    return value


def _frontmatter(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract only simple tags and aliases; do not execute YAML object tags."""
    if not text.startswith('---\n'):
        return (), ()
    end = text.find('\n---\n', 4, 8192)
    if end < 0:
        return (), ()
    parsed: dict[str, list[str]] = {'tags': [], 'aliases': []}
    active = None
    for line in text[4:end].splitlines():
        match = re.match(r'^([A-Za-z]+):\s*(.*?)\s*$', line)
        if match:
            key, value = match.groups()
            active = key if key in parsed else None
            if active and value:
                raw = value[1:-1] if value.startswith('[') and value.endswith(']') else value
                parsed[active].extend(x.strip().strip('"\'') for x in raw.split(',') if x.strip())
        elif active and re.match(r'^\s+-\s+\S', line):
            parsed[active].append(line.split('-', 1)[1].strip().strip('"\''))
        else:
            active = None
    return tuple(dict.fromkeys(x.lstrip('#') for x in parsed['tags'] if x)), tuple(dict.fromkeys(x for x in parsed['aliases'] if x))


def _links_and_tags(text: str) -> tuple[tuple[Link, ...], tuple[str, ...]]:
    links: list[Link] = []
    tags: list[str] = []
    in_fence = False
    tick = chr(96)
    for number, line in enumerate(text.splitlines(), 1):
        if re.match(r'^\s*(' + re.escape(tick) + r'{3}|~~~)', line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        visible = re.sub(re.escape(tick) + r'[^' + re.escape(tick) + r']*' + re.escape(tick), '', line)
        for m in WIKI.finditer(visible):
            raw = m.group(1).split('|', 1)[0].split('#', 1)[0].strip()
            if raw:
                links.append(Link(raw, number, 'wikilink'))
        for m in MARKDOWN.finditer(visible):
            raw = m.group(1).strip().split('#', 1)[0].split('?', 1)[0]
            if raw:
                links.append(Link(raw, number, 'markdown'))
        tags.extend(m.group(1) for m in TAG.finditer(visible))
    return tuple(links), tuple(dict.fromkeys(tags))


class ObsidianVaultBridge:
    """Ephemeral read-only note index; never writes the user's Obsidian vault."""

    def __init__(self, vault: str | Path, *, max_notes: int = MAX_NOTES,
                 max_note_bytes: int = MAX_NOTE_BYTES, max_total_bytes: int = MAX_TOTAL_BYTES):
        self.root = Path(vault).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('vault must be an existing directory')
        for value in (max_notes, max_note_bytes, max_total_bytes):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError('positive finite budgets required')
        self.max_notes, self.max_note_bytes, self.max_total_bytes = max_notes, max_note_bytes, max_total_bytes

    def _read(self, relative: str) -> bytes:
        relative = _safe_relative(relative)
        if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
            raise RuntimeError('secure vault reader requires openat O_NOFOLLOW support')
        flags_dir = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        flags_file = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, 'O_NONBLOCK', 0)
        fd = os.open(self.root, flags_dir)
        try:
            parts = relative.split('/')
            for segment in parts[:-1]:
                child = os.open(segment, flags_dir, dir_fd=fd)
                os.close(fd)
                fd = child
            note = os.open(parts[-1], flags_file, dir_fd=fd)
            try:
                st = os.fstat(note)
                if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > self.max_note_bytes:
                    raise ValueError('note is not a bounded regular unaliased file')
                with os.fdopen(os.dup(note), 'rb') as stream:
                    raw = stream.read(self.max_note_bytes + 1)
                if len(raw) > self.max_note_bytes or os.fstat(note).st_size != len(raw):
                    raise ValueError('note changed or exceeded read budget')
                return raw
            finally:
                os.close(note)
        finally:
            os.close(fd)

    def read(self) -> dict:
        files: list[str] = []
        omissions: list[dict] = []
        for directory, dirs, names in os.walk(self.root, topdown=True, followlinks=False):
            current = Path(directory)
            dirs[:] = sorted(d for d in dirs if d not in IGNORE and not d.startswith('.')
                             and not (current / d).is_symlink())
            for filename in sorted(names):
                if filename.startswith('.') or not filename.lower().endswith('.md'):
                    continue
                path = current / filename
                relative = path.relative_to(self.root).as_posix()
                if len(files) >= self.max_notes:
                    omissions.append({'path': relative, 'reason': 'note_count_limit'})
                    continue
                if path.is_symlink():
                    omissions.append({'path': relative, 'reason': 'symlink_disallowed'})
                    continue
                files.append(relative)
        notes: dict[str, Note] = {}
        remaining = self.max_total_bytes
        for rel in sorted(files):
            try:
                raw = self._read(rel)
                if len(raw) > remaining:
                    raise ValueError('total_byte_limit')
                remaining -= len(raw)
                text = raw.decode('utf-8')
                tags, aliases = _frontmatter(text)
                links, inline_tags = _links_and_tags(text)
                notes[rel] = Note(rel, Path(rel).stem, hashlib.sha256(raw).hexdigest(),
                                  tuple(dict.fromkeys((*tags, *inline_tags))), aliases, links)
            except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
                omissions.append({'path': rel, 'reason': 'unreadable_or_unbounded_' + type(exc).__name__})
        names: dict[str, set[str]] = {}
        for path, note in notes.items():
            for name in (path[:-3], note.title, *note.aliases):
                names.setdefault(name.casefold(), set()).add(path)
        edges: set[tuple[str, str]] = set()
        unresolved: list[dict] = []
        for source, note in notes.items():
            for link in note.links:
                raw = unquote(link.target).strip().replace('\\', '/')
                if not raw or raw.startswith('/') or '://' in raw or '\x00' in raw:
                    unresolved.append({'source': source, 'line': link.line, 'reason': 'unsupported_target'})
                    continue
                path = raw[:-3] if raw.lower().endswith('.md') else raw
                if link.style == 'markdown':
                    path = (PurePosixPath(source).parent / path).as_posix()
                segments = []
                for part in path.split('/'):
                    if part in ('', '.'):
                        continue
                    if part == '..':
                        if not segments:
                            segments = []
                            break
                        segments.pop()
                    else:
                        segments.append(part)
                norm = '/'.join(segments)
                if not norm or norm.startswith('.'):
                    unresolved.append({'source': source, 'line': link.line, 'reason': 'invalid_target'})
                    continue
                candidates = names.get(norm.casefold(), set())
                if len(candidates) == 1:
                    edges.add((source, next(iter(candidates))))
                else:
                    unresolved.append({'source': source, 'line': link.line,
                                       'reason': 'ambiguous' if candidates else 'unresolved'})
        backs: dict[str, list[str]] = {path: [] for path in notes}
        for source, target in sorted(edges):
            backs[target].append(source)
        summary = [{'path': path, 'title': note.title, 'sha256': note.sha256,
                    'tags': list(note.tags), 'aliases': list(note.aliases),
                    'outlinks': sorted(target for src, target in edges if src == path),
                    'backlinks': backs[path]}
                   for path, note in sorted(notes.items())]
        return {'schema': 'merlin-obsidian-vault-read/1', 'notes': summary,
                'links': [{'source': src, 'target': tgt} for src, tgt in sorted(edges)],
                'unresolved': unresolved, 'omissions': sorted(omissions, key=lambda x: x['path']),
                'notes_scanned': len(notes), 'source_bytes_scanned': self.max_total_bytes - remaining,
                'status': 'partial' if omissions else 'indexed', 'source_content_emitted': False,
                'persistent_memory_changed': False, 'production_qualified': False}

    def search(self, query: str, *, limit: int = 10, include_snippets: bool = False) -> dict:
        if not isinstance(query, str) or not 1 <= len(query) <= 160 or not query.strip():
            raise ValueError('bounded search query required')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('search limit must be 1-100')
        terms = [t.casefold() for t in WORD.findall(query)][:12]
        if not terms:
            return {'schema': 'merlin-obsidian-search/1', 'results': [], 'query': query}
        inventory = self.read()
        results = []
        for note in inventory['notes']:
            fresh = self._read(note['path'])
            if hashlib.sha256(fresh).hexdigest() != note['sha256']:
                raise RuntimeError('vault note changed during search; retry with a fresh index')
            content = fresh.decode('utf-8')
            matchline = next((i for i, line in enumerate(content.splitlines(), 1)
                              if all(term in line.casefold() for term in terms)), None)
            label = (note['title'] + ' ' + note['path'] + ' ' + ' '.join(note['tags'])).casefold()
            if matchline is None and not all(t in label for t in terms):
                continue
            score = sum(3 if t in note['title'].casefold() else 2 if t in label else 1 for t in terms)
            entry = {'path': note['path'], 'sha256': note['sha256'], 'line': matchline,
                     'relevance_rank_score': score, 'backlink_count': len(note['backlinks'])}
            if include_snippets and matchline:
                entry['snippet'] = content.splitlines()[matchline - 1][:200]
            results.append(entry)
        results.sort(key=lambda x: (-x['relevance_rank_score'], x['path']))
        return {'schema': 'merlin-obsidian-search/1', 'query': query,
                'results': results[:limit], 'limit': limit,
                'source_content_emitted': bool(include_snippets),
                'persistent_memory_changed': False, 'production_qualified': False}
