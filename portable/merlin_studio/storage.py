"""Durable Studio state alongside Merlin's canonical artifact registry."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import threading
import uuid

# Development checkout and packaged core both use the original registry code.
HERE = Path(__file__).resolve().parent
for candidate in (HERE / "core" / "python", HERE.parents[1] / "python"):
    if (candidate / "merlin" / "project_registry.py").is_file():
        sys.path.insert(0, str(candidate))
        break
from merlin.project_registry import MerlinRegistry


def now():
    return datetime.now(timezone.utc).isoformat()


def identity():
    return uuid.uuid4().hex


def bounded_preview(value, *, string_bytes=8192, depth=0):
    """Small UI/model preview; the canonical artifact retains complete bytes."""
    if depth > 8:
        return "[nested content retained in artifact]"
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return value if len(raw) <= string_bytes else raw[:string_bytes].decode("utf-8", "ignore") + "\n[preview truncated]"
    if isinstance(value, dict):
        return {str(k): bounded_preview(v, string_bytes=string_bytes, depth=depth + 1)
                for k, v in list(value.items())[:32]}
    if isinstance(value, list):
        return [bounded_preview(v, string_bytes=string_bytes, depth=depth + 1) for v in value[:32]]
    return value


class Store:
    PROJECT = "merlin-studio-local"

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = MerlinRegistry(self.root / "registry")
        self.registry.register_project(self.PROJECT, "Merlin Studio", "0.2.0")
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS studio_conversations(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_messages(
              ordinal INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
              conversation_id TEXT NOT NULL REFERENCES studio_conversations(id),
              role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_runs(
              id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES studio_conversations(id),
              status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              error TEXT, approval_json TEXT, approval_answer INTEGER);
            CREATE TABLE IF NOT EXISTS studio_events(
              ordinal INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
              run_id TEXT NOT NULL REFERENCES studio_runs(id), payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS studio_settings(
              id INTEGER PRIMARY KEY CHECK(id=1), payload_json TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS studio_messages_conversation
              ON studio_messages(conversation_id, ordinal);
            CREATE INDEX IF NOT EXISTS studio_events_run ON studio_events(run_id, ordinal);
            """)

    @contextmanager
    def db(self):
        with self.lock:
            db = sqlite3.connect(self.registry.db_path, timeout=15)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            try:
                with db:
                    yield db
            finally:
                db.close()

    def recover_interrupted(self):
        """A restart records unfinished work; side effects are never replayed."""
        with self.db() as db:
            ids = [r[0] for r in db.execute(
                "SELECT id FROM studio_runs WHERE status IN ('running','waiting_approval')")]
            for run_id in ids:
                db.execute("UPDATE studio_runs SET status='interrupted', error=?, "
                           "approval_json=NULL, updated_at=? WHERE id=?",
                           ("Server restarted. Review the saved activity before starting a new request.", now(), run_id))
                self._event(db, run_id, "interrupted", content="Server restarted; no action was replayed.")
        return ids

    def create_conversation(self, title="New conversation"):
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            raise ValueError("Conversation title must contain 1–120 characters")
        value = {"id": identity(), "title": title.strip(), "created_at": now(), "updated_at": now()}
        with self.db() as db:
            db.execute("INSERT INTO studio_conversations VALUES(:id,:title,:created_at,:updated_at)", value)
        return self.conversation(value["id"])

    def conversations(self):
        with self.db() as db:
            return [dict(r) for r in db.execute(
                "SELECT * FROM studio_conversations ORDER BY updated_at DESC LIMIT 200")]

    def conversation(self, conversation_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM studio_conversations WHERE id=?", (conversation_id,)).fetchone()
            if row is None:
                raise KeyError("Conversation not found")
            result = dict(row)
            result["messages"] = [dict(r) for r in db.execute(
                "SELECT id,role,content,created_at FROM studio_messages WHERE conversation_id=? "
                "ORDER BY ordinal", (conversation_id,))]
            last = db.execute("SELECT id FROM studio_runs WHERE conversation_id=? ORDER BY created_at DESC LIMIT 1",
                              (conversation_id,)).fetchone()
        result["events"] = self.events(last[0]) if last else []
        result["last_run_id"] = last[0] if last else None
        return result

    def _message(self, db, conversation_id, role, content):
        db.execute("INSERT INTO studio_messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",
                   (identity(), conversation_id, role, content, now()))
        db.execute("UPDATE studio_conversations SET updated_at=? WHERE id=?", (now(), conversation_id))

    def start_run(self, conversation_id, message):
        if not isinstance(message, str) or not 0 < len(message.strip()) <= 32768:
            raise ValueError("Message must contain 1–32768 characters")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT title FROM studio_conversations WHERE id=?", (conversation_id,)).fetchone()
            if row is None:
                raise KeyError("Conversation not found")
            if db.execute("SELECT 1 FROM studio_runs WHERE conversation_id=? AND "
                          "status IN ('running','waiting_approval')", (conversation_id,)).fetchone():
                raise ValueError("This conversation already has an active request")
            if row[0] == "New conversation":
                db.execute("UPDATE studio_conversations SET title=? WHERE id=?", (message.strip()[:70], conversation_id))
            self._message(db, conversation_id, "user", message.strip())
            run_id = identity()
            db.execute("INSERT INTO studio_runs VALUES(?,?,?,?,?,NULL,NULL,NULL)",
                       (run_id, conversation_id, "running", now(), now()))
            self._event(db, run_id, "started", content="Request started")
        return run_id

    def _event(self, db, run_id, event_type, **details):
        event = {"id": identity(), "type": event_type, "created_at": now(), **details}
        encoded = json.dumps(event, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 160000:
            raise ValueError("Event exceeds storage limit")
        db.execute("INSERT INTO studio_events(id,run_id,payload_json) VALUES(?,?,?)", (event["id"], run_id, encoded))
        return event

    def event(self, run_id, event_type, **details):
        encoded = json.dumps(details, ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > 120000:
            ref = self.artifact("studio/events/" + run_id + "/" + identity() + ".json", details)
            preview = bounded_preview(details, string_bytes=4096)
            if len(json.dumps(preview, ensure_ascii=False).encode()) > 120000:
                preview = {"content": "Large event retained in the linked artifact", "tool": details.get("tool")}
            details = {**preview, "truncated": True, "full_event_artifact_ref": ref}
        with self.db() as db:
            return self._event(db, run_id, event_type, **details)

    def events(self, run_id):
        with self.db() as db:
            return [json.loads(r[0]) for r in db.execute(
                "SELECT payload_json FROM studio_events WHERE run_id=? ORDER BY ordinal", (run_id,))]

    def run(self, run_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM studio_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError("Request not found")
            result = dict(row)
        approval = result.pop("approval_json")
        result["pending_approval"] = json.loads(approval) if approval and result["status"] == "waiting_approval" else None
        result.pop("approval_answer")
        result["events"] = self.events(run_id)
        return result

    def active(self, run_id):
        with self.db() as db:
            row = db.execute("SELECT status FROM studio_runs WHERE id=?", (run_id,)).fetchone()
            return row is not None and row[0] in ("running", "waiting_approval")

    def finish(self, run_id, content=None, *, status="completed", error=None):
        if status not in ("completed", "failed", "cancelled"):
            raise ValueError("Invalid terminal status")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT conversation_id,status FROM studio_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError("Request not found")
            if row[1] not in ("running", "waiting_approval"):
                return False
            if content is not None:
                self._message(db, row[0], "assistant", content)
            db.execute("UPDATE studio_runs SET status=?,error=?,approval_json=NULL,updated_at=? WHERE id=?",
                       (status, error, now(), run_id))
            self._event(db, run_id, status, content=error or "Request " + status)
        return True

    def request_approval(self, run_id, tool, arguments):
        approval = {"id": identity(), "tool": tool, "arguments": arguments}
        with self.db() as db:
            result = db.execute("UPDATE studio_runs SET status='waiting_approval',approval_json=?, "
                                "approval_answer=NULL,updated_at=? WHERE id=? AND status='running'",
                                (json.dumps(approval), now(), run_id))
            if result.rowcount != 1:
                raise RuntimeError("Request is no longer active")
            self._event(db, run_id, "approval_required", **approval)
        return approval["id"]

    def approve(self, run_id, approval_id, approved):
        if type(approved) is not bool:
            raise ValueError("Approval must be true or false")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status,approval_json,approval_answer FROM studio_runs WHERE id=?", (run_id,)).fetchone()
            if not row or row[0] != "waiting_approval" or not row[1] or json.loads(row[1])["id"] != approval_id:
                raise ValueError("Approval expired or does not match this action")
            db.execute("UPDATE studio_runs SET status='running',approval_answer=?,updated_at=? WHERE id=?",
                       (int(approved), now(), run_id))
            self._event(db, run_id, "approval_decided", approved=approved, approval_id=approval_id)

    def approval_answer(self, run_id, approval_id):
        """Consume a decided approval once; polling an undecided one is read-only."""
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT approval_json,approval_answer FROM studio_runs WHERE id=?", (run_id,)).fetchone()
            if not row or not row[0] or json.loads(row[0])["id"] != approval_id:
                return None
            if row[1] is None:
                return None
            db.execute("UPDATE studio_runs SET approval_json=NULL,approval_answer=NULL WHERE id=?", (run_id,))
            return bool(row[1])

    def settings(self):
        with self.db() as db:
            row = db.execute("SELECT payload_json FROM studio_settings WHERE id=1").fetchone()
            return json.loads(row[0]) if row else {}

    def save_settings(self, settings):
        with self.db() as db:
            db.execute("INSERT INTO studio_settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload_json=excluded.payload_json",
                       (json.dumps(settings, allow_nan=False),))

    def artifact(self, logical_path, content, media_type="application/json"):
        if not isinstance(content, bytes):
            content = json.dumps(content, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
        with self.lock:
            digest = self.registry.put_artifact(self.PROJECT, logical_path, content, media_type)
            # Bind our bytes even if another process advances this logical path.
            history = self.registry.artifact_history(self.PROJECT, logical_path)
            version = next(item["version"] for item in reversed(history) if item["digest"] == digest)
            ref = self.registry.artifact_ref(self.PROJECT, logical_path, version)
            if ref["sha256"] != digest:
                raise RuntimeError("Artifact publication identity differs")
            return ref
