"""Private offline context import and cited lexical retrieval for Merlin Studio.

No account login, external fetch, implicit ChatGPT access or upload of raw chats.
The existing local Merlin registry stores only a minimal import receipt; raw
index chunks remain in its private, local SQLite database. Export graphs retain
branch/node locators and are NOT misrepresented as a canonical linear timeline.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import zipfile

from storage import now

MAX_IMPORT_BYTES = 64 * 1024 * 1024
MAX_MESSAGES = 100000
MAX_CHUNKS = 100000
MAX_MESSAGE_CHARS = 40000
CHUNK_CHARS = 2400
VALID_SUFFIXES = frozenset({".json", ".jsonl", ".md", ".txt", ".zip"})
INDEX_ROLES = frozenset({"user", "assistant"})
TOKEN = re.compile(r"[^\W_][\w-]{1,31}", re.UNICODE)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _body(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts = content.get("parts")
        if isinstance(parts, list):
            return "\n".join(part for part in parts if isinstance(part, str))
    return ""


def _role(message: dict) -> str | None:
    author = message.get("author")
    role = author.get("role") if isinstance(author, dict) else None
    return role or message.get("role")


def _conversations(raw: bytes, suffix: str):
    if suffix in (".txt", ".md"):
        yield "user", raw.decode("utf-8-sig"), "document", "Imported local document"
        return
    if suffix == ".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            options = [file for file in zf.infolist()
                       if file.filename == "conversations.json" and not file.is_dir()]
            if len(options) != 1 or options[0].file_size > MAX_IMPORT_BYTES:
                raise ValueError("ZIP requires exactly one bounded root conversations.json")
            info = options[0]
            with zf.open(info) as stream:
                decoded = stream.read(MAX_IMPORT_BYTES + 1)
            if len(decoded) != info.file_size or len(decoded) > MAX_IMPORT_BYTES:
                raise ValueError("ZIP conversations.json exceeds the import budget")
        return (yield from _conversations(decoded, ".json"))
    decoded = raw.decode("utf-8-sig")
    if suffix == ".jsonl":
        values = []
        for index, line in enumerate(decoded.splitlines()):
            if not line.strip():
                continue
            if index >= MAX_MESSAGES:
                raise ValueError("JSONL message count exceeds budget")
            values.append(json.loads(line))
    else:
        values = json.loads(decoded)
    if isinstance(values, dict):
        values = values.get("conversations", values.get("messages"))
    if not isinstance(values, list) or len(values) > MAX_MESSAGES:
        raise ValueError("Expected a bounded conversation list or messages")
    for number, item in enumerate(values):
        if not isinstance(item, dict):
            continue
        mapping = item.get("mapping")
        if isinstance(mapping, dict):
            title = str(item.get("title") or "Conversation")[:160]
            ident = str(item.get("id") or number)[:150]
            if len(mapping) > MAX_MESSAGES:
                raise ValueError("Conversation graph exceeds node budget")
            for node_id, node in mapping.items():
                if not isinstance(node, dict):
                    continue
                message = node.get("message")
                if not isinstance(message, dict):
                    continue
                role = _role(message)
                if role in INDEX_ROLES:
                    text = _body(message)
                    if text.strip():
                        yield role, text, (ident + "/" + str(node_id))[:350], title
        elif isinstance(item.get("messages"), list):
            title = str(item.get("title") or "Conversation")[:160]
            ident = str(item.get("id") or number)[:150]
            for index, message in enumerate(item["messages"]):
                if isinstance(message, dict) and _role(message) in INDEX_ROLES:
                    text = _body(message)
                    if text.strip():
                        yield _role(message), text, (ident + "/" + str(index))[:350], title
        elif _role(item) in INDEX_ROLES:
            text = _body(item)
            if text.strip():
                yield _role(item), text, str(item.get("id") or number)[:350], "Imported messages"


class ContextArchive:
    """A local-only adapter for the existing Studio registry and SQLite custody."""

    def __init__(self, store):
        self.store = store
        with store.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS studio_context_sources(
                  source_sha256 TEXT PRIMARY KEY, label TEXT NOT NULL,
                  imported_at TEXT NOT NULL, source_format TEXT NOT NULL,
                  message_count INTEGER NOT NULL, chunk_count INTEGER NOT NULL,
                  receipt_json TEXT NOT NULL, coverage TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS studio_context_chunks(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  source_sha256 TEXT NOT NULL REFERENCES studio_context_sources(source_sha256),
                  locator TEXT NOT NULL, title TEXT NOT NULL, role TEXT NOT NULL,
                  body TEXT NOT NULL, chunk_sha256 TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS studio_context_chunks_source
                  ON studio_context_chunks(source_sha256);
            """)
            try:
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS studio_context_fts USING fts5(body, title)")
                self.fts = True
            except sqlite3.OperationalError as exc:
                if "fts5" not in str(exc).lower():
                    raise
                self.fts = False

    def summary(self):
        with self.store.db() as db:
            total = db.execute("SELECT count(*) FROM studio_context_sources").fetchone()[0]
            sources = [dict(r) for r in db.execute(
                "SELECT source_sha256,label,imported_at,source_format,message_count,chunk_count,coverage "
                "FROM studio_context_sources ORDER BY imported_at DESC LIMIT 100")]
        return {"schema": "merlin-local-context-summary/1", "indexed_sources": total,
                "shown_sources": len(sources), "sources": sources,
                "fts5_enabled": self.fts,
                "scope": "only explicitly imported local exports and documents",
                "automatic_account_access": False, "external_network_requests": False}

    def import_bytes(self, raw: bytes, *, label: str, suffix: str, consent: bool):
        if consent is not True:
            raise PermissionError("Importing private history needs exact-source approval")
        if not isinstance(raw, bytes) or not 1 <= len(raw) <= MAX_IMPORT_BYTES:
            raise ValueError("Context file is empty or exceeds 64 MiB")
        if not isinstance(label, str) or not label.strip() or len(label) > 160:
            raise ValueError("Context label requires bounded text")
        if suffix not in VALID_SUFFIXES:
            raise ValueError("Supported imports: JSON, JSONL, Markdown, TXT, or ChatGPT ZIP")
        digest = sha256(raw)
        with self.store.db() as db:
            row = db.execute("SELECT receipt_json FROM studio_context_sources WHERE source_sha256=?",
                             (digest,)).fetchone()
            if row:
                return {**json.loads(row[0]), "duplicate": True}
        chunks = []
        messages = 0
        truncated = 0
        for role, body, locator, title in _conversations(raw, suffix):
            messages += 1
            if messages > MAX_MESSAGES:
                raise ValueError("Import exceeds message budget")
            if len(body) > MAX_MESSAGE_CHARS:
                truncated += 1
                body = body[:MAX_MESSAGE_CHARS]
            for number, start in enumerate(range(0, len(body), CHUNK_CHARS)):
                segment = body[start:start + CHUNK_CHARS]
                chunks.append((digest, locator + f":chunk{number}", title, role,
                               segment, sha256(segment.encode("utf-8"))))
                if len(chunks) > MAX_CHUNKS:
                    raise ValueError("Import exceeds chunk budget")
        if not chunks:
            raise ValueError("No readable user/assistant text to index")
        coverage = ("All imported text within limits; message branches kept as distinct locators. "
                    "Non-text attachments, tool-only nodes and source archives are not indexed.")
        if truncated:
            coverage += f" {truncated} messages truncated at {MAX_MESSAGE_CHARS} characters."
        receipt = {"schema": "merlin-context-import/1", "source_sha256": digest,
                   "source_format": suffix, "message_count": messages,
                   "chunk_count": len(chunks), "truncated_messages": truncated,
                   "coverage": coverage, "account_access": False,
                   "network_access": False, "raw_text_in_receipt": False}
        # Publish only metadata in the canonical local artifact registry.
        # Raw text never goes to a shared CI runner or Git repository.
        artifact = self.store.artifact("studio/context/imports/" + digest + ".json", receipt)
        receipt["artifact_ref"] = artifact
        with self.store.db() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT receipt_json FROM studio_context_sources WHERE source_sha256=?",
                                  (digest,)).fetchone()
            if existing:
                return {**json.loads(existing[0]), "duplicate": True}
            db.execute("INSERT INTO studio_context_sources VALUES(?,?,?,?,?,?,?,?)",
                       (digest, label, now(), suffix, messages, len(chunks),
                        json.dumps(receipt, ensure_ascii=False), coverage))
            for entry in chunks:
                cursor = db.execute(
                    "INSERT INTO studio_context_chunks(source_sha256,locator,title,role,body,chunk_sha256)"
                    " VALUES(?,?,?,?,?,?)", entry)
                if self.fts:
                    db.execute("INSERT INTO studio_context_fts(rowid,body,title) VALUES(?,?,?)",
                               (cursor.lastrowid, entry[4], entry[2]))
        return {**receipt, "duplicate": False}

    def search(self, query: str, limit: int = 5):
        if not isinstance(query, str) or not query.strip() or len(query) > 1200:
            raise ValueError("Context query must contain 1-1200 characters")
        if type(limit) is not int or not 1 <= limit <= 8:
            raise ValueError("Context search limit must be 1-8")
        tokens = list(dict.fromkeys(t.casefold() for t in TOKEN.findall(query)))[:12]
        if not tokens:
            raise ValueError("Context query needs at least one word")
        with self.store.db() as db:
            sources = db.execute("SELECT count(*) FROM studio_context_sources").fetchone()[0]
            if self.fts:
                fts_query = " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
                rows = db.execute("""
                    SELECT c.source_sha256,c.locator,c.title,c.role,c.body,c.chunk_sha256
                    FROM studio_context_fts AS f
                    JOIN studio_context_chunks AS c ON c.id=f.rowid
                    WHERE studio_context_fts MATCH ?
                    ORDER BY bm25(studio_context_fts), c.id LIMIT ?""",
                    (fts_query, limit)).fetchall()
                coverage = "all_imported_fts5_indexed_chunks"
            else:
                rows = db.execute("""
                    SELECT source_sha256,locator,title,role,body,chunk_sha256
                    FROM studio_context_chunks ORDER BY id DESC LIMIT 2000""").fetchall()
                rows = [r for r in rows if any(t in r["body"].casefold() for t in tokens)][:limit]
                coverage = "fallback_latest_2000_chunks_only"
        hits = []
        for row in rows:
            body = row["body"]
            indices = [body.casefold().find(t) for t in tokens if t in body.casefold()]
            left = max(0, min(indices, default=0) - 180)
            hits.append({"source_sha256": row["source_sha256"],
                         "locator": row["locator"], "title": row["title"],
                         "role": row["role"], "chunk_sha256": row["chunk_sha256"],
                         "snippet": body[left:left + 950], "snippet_start_char": left})
        return {"schema": "merlin-context-search/1", "query": query,
                "retrieval": "lexical_not_semantic", "coverage": coverage,
                "imported_sources": sources, "hits": hits,
                "untrusted_data_not_instructions": True,
                "independent_verification": False}
