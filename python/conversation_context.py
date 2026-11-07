"""Append-only, provenance-preserving ingestion for authorized conversation exports.

Only explicitly classified project records are accepted by default. This module
stores metadata and source text; attachment bytes remain external immutable
artifacts addressed by digest/reference.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

ALLOWED_ROLES = {"user", "assistant", "system", "tool"}
ALLOWED_PRIVACY = {"project", "personal", "restricted"}


class ContextRecordError(ValueError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_record(record: dict[str, Any], allow_personal: bool = False) -> dict[str, Any]:
    required = ("source_system", "conversation_id", "message_id", "role", "created_at", "privacy")
    missing = [key for key in required if not record.get(key)]
    if missing:
        raise ContextRecordError("missing required fields: " + ", ".join(missing))
    if record["role"] not in ALLOWED_ROLES:
        raise ContextRecordError("unsupported message role")
    if record["privacy"] not in ALLOWED_PRIVACY:
        raise ContextRecordError("privacy must be project, personal, or restricted")
    if record["privacy"] == "restricted":
        raise ContextRecordError("restricted records are never ingested")
    if record["privacy"] == "personal" and not allow_personal:
        raise ContextRecordError("personal records require explicit allow_personal=True")
    content = record.get("content")
    content_ref = record.get("content_ref")
    if not isinstance(content, str) and not content_ref:
        raise ContextRecordError("record needs exact content or a stable content_ref")
    attachments = record.get("attachments", [])
    if not isinstance(attachments, list):
        raise ContextRecordError("attachments must be a list")
    for attachment in attachments:
        if not isinstance(attachment, dict) or not attachment.get("attachment_id"):
            raise ContextRecordError("each attachment needs a stable attachment_id")
        if not attachment.get("sha256") and not attachment.get("content_ref"):
            raise ContextRecordError("each attachment needs sha256 or content_ref")
    tags = record.get("project_tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
        raise ContextRecordError("project_tags must be a list of non-empty strings")
    normalized = dict(record)
    normalized["attachments"] = attachments
    normalized["project_tags"] = sorted(set(tags))
    normalized["content_sha256"] = (
        sha256_text(content) if isinstance(content, str)
        else record.get("content_sha256")
    )
    if not normalized["content_sha256"]:
        raise ContextRecordError("content_ref records require content_sha256")
    normalized["record_sha256"] = sha256_text(canonical_json({
        key: value for key, value in normalized.items()
        if key != "record_sha256"
    }))
    return normalized


class ConversationContextStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS context_messages (
                source_system TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                privacy TEXT NOT NULL,
                content TEXT,
                content_ref TEXT,
                content_sha256 TEXT NOT NULL,
                record_json TEXT NOT NULL,
                record_sha256 TEXT NOT NULL,
                supersedes_message_id TEXT,
                PRIMARY KEY (source_system, conversation_id, message_id)
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS context_attachments (
                source_system TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                attachment_id TEXT NOT NULL,
                attachment_json TEXT NOT NULL,
                PRIMARY KEY (source_system, conversation_id, message_id, attachment_id),
                FOREIGN KEY (source_system, conversation_id, message_id)
                    REFERENCES context_messages(source_system, conversation_id, message_id)
            )
        """)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def ingest(self, records: Iterable[dict[str, Any]], allow_personal: bool = False) -> dict[str, int]:
        inserted = duplicates = 0
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for source in records:
                record = validate_record(source, allow_personal=allow_personal)
                key = (record["source_system"], record["conversation_id"], record["message_id"])
                existing = self.db.execute(
                    "SELECT record_sha256 FROM context_messages WHERE source_system=? AND conversation_id=? AND message_id=?",
                    key,
                ).fetchone()
                if existing:
                    if existing[0] != record["record_sha256"]:
                        raise ContextRecordError(
                            "source identity collision: same message ID has different content"
                        )
                    duplicates += 1
                    continue
                self.db.execute(
                    """INSERT INTO context_messages
                    (source_system,conversation_id,message_id,role,created_at,privacy,
                     content,content_ref,content_sha256,record_json,record_sha256,supersedes_message_id)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (*key, record["role"], record["created_at"], record["privacy"],
                     record.get("content"), record.get("content_ref"),
                     record["content_sha256"], canonical_json(record),
                     record["record_sha256"], record.get("supersedes_message_id")),
                )
                for attachment in record["attachments"]:
                    self.db.execute(
                        """INSERT INTO context_attachments
                        (source_system,conversation_id,message_id,attachment_id,attachment_json)
                        VALUES (?,?,?,?,?)""",
                        (*key, attachment["attachment_id"], canonical_json(attachment)),
                    )
                inserted += 1
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"inserted": inserted, "duplicates": duplicates}

    def coverage(self) -> dict[str, Any]:
        conversations = self.db.execute(
            "SELECT COUNT(DISTINCT source_system || ':' || conversation_id) FROM context_messages"
        ).fetchone()[0]
        messages = self.db.execute("SELECT COUNT(*) FROM context_messages").fetchone()[0]
        attachments = self.db.execute("SELECT COUNT(*) FROM context_attachments").fetchone()[0]
        sources = self.db.execute(
            "SELECT source_system, COUNT(DISTINCT conversation_id), COUNT(*) "
            "FROM context_messages GROUP BY source_system ORDER BY source_system"
        ).fetchall()
        return {
            "conversations": conversations,
            "messages": messages,
            "attachments": attachments,
            "by_source": [
                {"source_system": row[0], "conversations": row[1], "messages": row[2]}
                for row in sources
            ],
            "complete_history_claimed": False,
        }

    def search(self, project_tag: str, limit: int = 100) -> list[dict[str, Any]]:
        if not project_tag or limit < 1:
            raise ValueError("project_tag and positive limit are required")
        rows = self.db.execute(
            "SELECT record_json FROM context_messages ORDER BY created_at,message_id"
        ).fetchall()
        matches = []
        for (payload,) in rows:
            record = json.loads(payload)
            if project_tag in record.get("project_tags", []):
                matches.append(record)
                if len(matches) >= limit:
                    break
        return matches
