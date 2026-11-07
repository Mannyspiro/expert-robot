"""Local Virtual GitHub Forge: immutable commits, branches, PRs, merges and worker jobs.

This is an internal source-control and orchestration primitive. It stores
content-addressed file snapshots in SQLite and never shells out to Git.
Execution is deliberately separate: jobs are queued and leased, not executed
inside the Forge database process.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import sqlite3
import time
import uuid
from pathlib import PurePosixPath
from typing import Any


class ForgeError(RuntimeError):
    pass


class MergeConflict(ForgeError):
    def __init__(self, paths: list[str]):
        self.paths = paths
        super().__init__("merge conflicts: " + ", ".join(paths))


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_path(path: str) -> str:
    p = PurePosixPath(path)
    if not path or p.as_posix() == "." or p.is_absolute() or any(part in {"", ".", ".."} for part in p.parts):
        raise ForgeError(f"unsafe repository path: {path!r}")
    if "\\" in path or "\x00" in path:
        raise ForgeError(f"unsafe repository path: {path!r}")
    return p.as_posix()


def _edits(base: list[str], changed: list[str]) -> list[tuple[int, int, list[str]]]:
    matcher = difflib.SequenceMatcher(a=base, b=changed, autojunk=False)
    return [
        (i1, i2, changed[j1:j2])
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


def _three_way_text(base_text: str, ours_text: str, theirs_text: str) -> str | None:
    if ours_text == theirs_text:
        return ours_text
    if ours_text == base_text:
        return theirs_text
    if theirs_text == base_text:
        return ours_text
    base = base_text.splitlines(keepends=True)
    ours = _edits(base, ours_text.splitlines(keepends=True))
    theirs = _edits(base, theirs_text.splitlines(keepends=True))
    combined = list(ours)
    for edit in theirs:
        if edit in ours:
            continue
        a1, a2, _ = edit
        conflict = False
        for b1, b2, _ in ours:
            if a1 == a2 and b1 == b2:
                conflict = a1 == b1
            elif a1 == a2:
                conflict = b1 <= a1 < b2
            elif b1 == b2:
                conflict = a1 <= b1 < a2
            else:
                conflict = max(a1, b1) < min(a2, b2)
            if conflict:
                return None
        combined.append(edit)
    result = list(base)
    for start, end, replacement in sorted(combined, key=lambda item: (item[0], item[1]), reverse=True):
        result[start:end] = replacement
    return "".join(result)


class VirtualForge:
    def __init__(self, database: str):
        self.db = sqlite3.connect(database, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self._schema()

    def close(self) -> None:
        self.db.close()

    def _schema(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS blobs(
            digest TEXT PRIMARY KEY, content BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS commits(
            commit_id TEXT PRIMARY KEY, tree_json TEXT NOT NULL,
            parent1 TEXT, parent2 TEXT, message TEXT NOT NULL,
            author TEXT NOT NULL, created_at REAL NOT NULL,
            FOREIGN KEY(parent1) REFERENCES commits(commit_id),
            FOREIGN KEY(parent2) REFERENCES commits(commit_id)
        );
        CREATE TABLE IF NOT EXISTS branches(
            name TEXT PRIMARY KEY, head TEXT NOT NULL,
            updated_at REAL NOT NULL,
            FOREIGN KEY(head) REFERENCES commits(commit_id)
        );
        CREATE TABLE IF NOT EXISTS pull_requests(
            pr_id TEXT PRIMARY KEY, title TEXT NOT NULL,
            source_branch TEXT NOT NULL, target_branch TEXT NOT NULL,
            base_commit TEXT NOT NULL, head_commit TEXT NOT NULL,
            state TEXT NOT NULL, created_at REAL NOT NULL,
            merged_commit TEXT,
            FOREIGN KEY(base_commit) REFERENCES commits(commit_id),
            FOREIGN KEY(head_commit) REFERENCES commits(commit_id),
            FOREIGN KEY(merged_commit) REFERENCES commits(commit_id)
        );
        CREATE TABLE IF NOT EXISTS forge_events(
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
            payload_json TEXT NOT NULL, previous_hash TEXT NOT NULL,
            event_hash TEXT NOT NULL, created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs(
            job_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL, payload_json TEXT NOT NULL,
            status TEXT NOT NULL, priority INTEGER NOT NULL,
            created_at REAL NOT NULL, updated_at REAL NOT NULL,
            worker_id TEXT, lease_expires REAL, attempts INTEGER NOT NULL DEFAULT 0,
            result_json TEXT, log_text TEXT, artifact_digests_json TEXT
        );
        CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status, priority DESC, created_at);
        CREATE TABLE IF NOT EXISTS job_events(
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL, kind TEXT NOT NULL,
            payload_json TEXT NOT NULL, created_at REAL NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(job_id)
        );
        """)
        if not self.db.execute("SELECT 1 FROM branches WHERE name='main'").fetchone():
            self.db.execute("BEGIN IMMEDIATE")
            try:
                cid = self._insert_commit({}, None, None, "Initialize Virtual Forge", "system")
                self.db.execute(
                    "INSERT INTO branches(name,head,updated_at) VALUES('main',?,?)",
                    (cid, time.time()),
                )
                self._event("repository.initialized", {"branch": "main", "commit": cid})
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def _event(self, kind: str, payload: dict[str, Any]) -> None:
        previous = self.db.execute(
            "SELECT event_hash FROM forge_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        prev = previous[0] if previous else "0" * 64
        event_id, created = str(uuid.uuid4()), time.time()
        body = _json({"event_id": event_id, "kind": kind, "payload": payload,
                      "previous_hash": prev, "created_at": created})
        self.db.execute(
            "INSERT INTO forge_events(event_id,kind,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?)",
            (event_id, kind, _json(payload), prev, _sha(body.encode()), created),
        )

    def _insert_commit(self, tree: dict[str, str], parent1: str | None,
                       parent2: str | None, message: str, author: str) -> str:
        cid, created = str(uuid.uuid4()), time.time()
        self.db.execute(
            "INSERT INTO commits VALUES(?,?,?,?,?,?,?)",
            (cid, _json(tree), parent1, parent2, message, author, created),
        )
        return cid

    def _head(self, branch: str) -> str:
        row = self.db.execute("SELECT head FROM branches WHERE name=?", (branch,)).fetchone()
        if not row:
            raise ForgeError(f"unknown branch: {branch}")
        return row[0]

    def _tree(self, commit_id: str) -> dict[str, str]:
        row = self.db.execute("SELECT tree_json FROM commits WHERE commit_id=?", (commit_id,)).fetchone()
        if not row:
            raise ForgeError(f"unknown commit: {commit_id}")
        return json.loads(row[0])

    def _content(self, digest: str) -> str:
        row = self.db.execute("SELECT content FROM blobs WHERE digest=?", (digest,)).fetchone()
        if not row:
            raise ForgeError(f"missing blob: {digest}")
        return bytes(row[0]).decode("utf-8")

    def read_file(self, branch: str, path: str) -> str:
        path = _safe_path(path)
        tree = self._tree(self._head(branch))
        if path not in tree:
            raise ForgeError(f"file not found: {path}")
        return self._content(tree[path])

    def snapshot(self, branch: str) -> dict[str, str]:
        tree = self._tree(self._head(branch))
        return {path: self._content(digest) for path, digest in sorted(tree.items())}

    def export_snapshot(self, branch: str, destination: str) -> int:
        """Materialize a branch snapshot into a new/empty workspace directory."""
        from pathlib import Path

        root = Path(destination).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if any(root.iterdir()):
            raise ForgeError("workspace destination must be empty")
        files = self.snapshot(branch)
        for relative, content in files.items():
            target = (root / relative).resolve()
            if root not in target.parents:
                raise ForgeError(f"workspace path escapes destination: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="")
        return len(files)

    def branches(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT name,head,updated_at FROM branches ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]

    def pull_requests(self, state: str | None = None) -> list[dict[str, Any]]:
        if state is not None and state not in {"open", "merged", "closed"}:
            raise ForgeError("invalid pull request state")
        if state:
            rows = self.db.execute(
                "SELECT * FROM pull_requests WHERE state=? ORDER BY created_at DESC", (state,)
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT * FROM pull_requests ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_branch(self, name: str, from_branch: str = "main") -> str:
        if not name or name == "main":
            raise ForgeError("branch name must be non-empty and cannot replace main")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT 1 FROM branches WHERE name=?", (name,)).fetchone():
                raise ForgeError(f"branch already exists: {name}")
            head, now = self._head(from_branch), time.time()
            self.db.execute("INSERT INTO branches VALUES(?,?,?)", (name, head, now))
            self._event("branch.created", {"branch": name, "from": from_branch, "head": head})
            self.db.commit()
            return head
        except Exception:
            self.db.rollback()
            raise

    def commit(self, branch: str, files: dict[str, str | None], message: str,
               author: str = "merlin", expected_head: str | None = None) -> str:
        if not files or not message.strip():
            raise ForgeError("commit requires file changes and a message")
        normalized = {_safe_path(path): content for path, content in files.items()}
        self.db.execute("BEGIN IMMEDIATE")
        try:
            parent = self._head(branch)
            if expected_head is not None and parent != expected_head:
                raise ForgeError("stale branch head; refresh before committing")
            tree = self._tree(parent)
            changed = []
            for path, content in normalized.items():
                if content is None:
                    if path in tree:
                        del tree[path]
                        changed.append(path)
                    continue
                if not isinstance(content, str):
                    raise ForgeError("file content must be UTF-8 text or None for deletion")
                raw = content.encode("utf-8")
                digest = _sha(raw)
                self.db.execute("INSERT OR IGNORE INTO blobs(digest,content) VALUES(?,?)", (digest, raw))
                if tree.get(path) != digest:
                    tree[path] = digest
                    changed.append(path)
            if not changed:
                raise ForgeError("commit contains no effective changes")
            cid = self._insert_commit(tree, parent, None, message, author)
            self.db.execute("UPDATE branches SET head=?,updated_at=? WHERE name=?",
                            (cid, time.time(), branch))
            self._event("commit.created", {"branch": branch, "commit": cid,
                                           "parent": parent, "files": sorted(changed)})
            self.db.commit()
            return cid
        except Exception:
            self.db.rollback()
            raise

    def _ancestors(self, commit_id: str) -> dict[str, int]:
        distances, pending = {}, [(commit_id, 0)]
        while pending:
            current, depth = pending.pop(0)
            if current in distances and distances[current] <= depth:
                continue
            distances[current] = depth
            row = self.db.execute("SELECT parent1,parent2 FROM commits WHERE commit_id=?", (current,)).fetchone()
            if row:
                for parent in (row[0], row[1]):
                    if parent:
                        pending.append((parent, depth + 1))
        return distances

    def _merge_base(self, left: str, right: str) -> str:
        a, b = self._ancestors(left), self._ancestors(right)
        common = set(a) & set(b)
        if not common:
            raise ForgeError("branches have no common ancestor")
        return min(common, key=lambda cid: a[cid] + b[cid])

    def open_pull_request(self, source_branch: str, target_branch: str = "main",
                          title: str = "Untitled change") -> str:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            source, target = self._head(source_branch), self._head(target_branch)
            if source == target:
                raise ForgeError("cannot open an empty pull request")
            pr = str(uuid.uuid4())
            self.db.execute(
                "INSERT INTO pull_requests VALUES(?,?,?,?,?,?,?, ?,NULL)",
                (pr, title, source_branch, target_branch, self._merge_base(source, target),
                 source, "open", time.time()),
            )
            self._event("pull_request.opened", {"pr": pr, "source": source_branch,
                                                 "target": target_branch, "head": source,
                                                 "base": target})
            self.db.commit()
            return pr
        except Exception:
            self.db.rollback()
            raise

    def _merge_trees(self, base_id: str, ours_id: str, theirs_id: str) -> tuple[dict[str, str], list[str]]:
        base, ours, theirs = self._tree(base_id), self._tree(ours_id), self._tree(theirs_id)
        result, conflicts = {}, []
        for path in sorted(set(base) | set(ours) | set(theirs)):
            b, o, t = base.get(path), ours.get(path), theirs.get(path)
            if o == t:
                chosen = o
            elif o == b:
                chosen = t
            elif t == b:
                chosen = o
            elif b is None or o is None or t is None:
                conflicts.append(path)
                continue
            else:
                merged = _three_way_text(self._content(b), self._content(o), self._content(t))
                if merged is None:
                    conflicts.append(path)
                    continue
                raw = merged.encode("utf-8")
                chosen = _sha(raw)
                self.db.execute("INSERT OR IGNORE INTO blobs(digest,content) VALUES(?,?)", (chosen, raw))
            if chosen is not None:
                result[path] = chosen
        return result, conflicts

    def merge_pull_request(self, pr_id: str, author: str = "merlin") -> str:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            pr = self.db.execute("SELECT * FROM pull_requests WHERE pr_id=?", (pr_id,)).fetchone()
            if not pr or pr["state"] != "open":
                raise ForgeError("pull request does not exist or is not open")
            target_head, source_head = self._head(pr["target_branch"]), self._head(pr["source_branch"])
            base_id = self._merge_base(target_head, source_head)
            tree, conflicts = self._merge_trees(base_id, target_head, source_head)
            if conflicts:
                raise MergeConflict(conflicts)
            cid = self._insert_commit(tree, target_head, source_head,
                                      f"Merge {pr['source_branch']} into {pr['target_branch']}", author)
            self.db.execute("UPDATE branches SET head=?,updated_at=? WHERE name=?",
                            (cid, time.time(), pr["target_branch"]))
            self.db.execute("UPDATE pull_requests SET state='merged',merged_commit=? WHERE pr_id=?",
                            (cid, pr_id))
            self._event("pull_request.merged", {"pr": pr_id, "commit": cid,
                                                "target": pr["target_branch"],
                                                "source": pr["source_branch"]})
            self.db.commit()
            return cid
        except Exception:
            self.db.rollback()
            raise

    def rollback_branch(self, branch: str, target_commit: str, author: str = "merlin") -> str:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._head(branch)
            target_tree = self._tree(target_commit)
            cid = self._insert_commit(target_tree, current, None,
                                      f"Rollback {branch} to snapshot {target_commit}", author)
            self.db.execute("UPDATE branches SET head=?,updated_at=? WHERE name=?",
                            (cid, time.time(), branch))
            self._event("branch.rolled_back", {"branch": branch, "from": current,
                                               "snapshot": target_commit, "commit": cid})
            self.db.commit()
            return cid
        except Exception:
            self.db.rollback()
            raise

    def enqueue_job(self, kind: str, payload: dict[str, Any],
                    idempotency_key: str, priority: int = 0) -> str:
        if not kind or not idempotency_key:
            raise ForgeError("job kind and idempotency key are required")
        now, job_id = time.time(), str(uuid.uuid4())
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing = self.db.execute("SELECT job_id FROM jobs WHERE idempotency_key=?",
                                       (idempotency_key,)).fetchone()
            if existing:
                self.db.commit()
                return existing[0]
            self.db.execute(
                """INSERT INTO jobs(job_id,idempotency_key,kind,payload_json,status,priority,
                   created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                (job_id, idempotency_key, kind, _json(payload), "queued", priority, now, now),
            )
            self.db.execute("INSERT INTO job_events(job_id,kind,payload_json,created_at) VALUES(?,?,?,?)",
                            (job_id, "queued", _json({"kind": kind}), now))
            self._event("job.queued", {"job_id": job_id, "kind": kind, "priority": priority})
            self.db.commit()
            return job_id
        except Exception:
            self.db.rollback()
            raise

    def claim_job(self, worker_id: str, lease_seconds: int = 300,
                  allowed_kinds: list[str] | None = None) -> dict[str, Any] | None:
        if not worker_id or lease_seconds < 1:
            raise ForgeError("worker ID and positive lease are required")
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.db.execute(
                "UPDATE jobs SET status='queued',worker_id=NULL,lease_expires=NULL,updated_at=? "
                "WHERE status='leased' AND lease_expires<?", (now, now),
            )
            query = "SELECT * FROM jobs WHERE status='queued'"
            args: list[Any] = []
            if allowed_kinds:
                query += " AND kind IN (" + ",".join("?" for _ in allowed_kinds) + ")"
                args.extend(allowed_kinds)
            query += " ORDER BY priority DESC,created_at LIMIT 1"
            row = self.db.execute(query, args).fetchone()
            if not row:
                self.db.commit()
                return None
            expires = now + lease_seconds
            self.db.execute(
                "UPDATE jobs SET status='leased',worker_id=?,lease_expires=?,attempts=attempts+1,updated_at=? WHERE job_id=?",
                (worker_id, expires, now, row["job_id"]),
            )
            self.db.execute("INSERT INTO job_events(job_id,kind,payload_json,created_at) VALUES(?,?,?,?)",
                            (row["job_id"], "leased", _json({"worker_id": worker_id,
                                                            "lease_expires": expires}), now))
            self.db.commit()
            return {"job_id": row["job_id"], "kind": row["kind"],
                    "payload": json.loads(row["payload_json"]), "worker_id": worker_id,
                    "lease_expires": expires, "attempt": row["attempts"] + 1}
        except Exception:
            self.db.rollback()
            raise

    def finish_job(self, job_id: str, worker_id: str, result: dict[str, Any],
                   log_text: str, artifact_digests: list[str] | None = None,
                   success: bool = True) -> None:
        now = time.time()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row or row["status"] != "leased" or row["worker_id"] != worker_id:
                raise ForgeError("job lease is missing, expired or owned by another worker")
            if row["lease_expires"] < now:
                raise ForgeError("job lease has expired")
            status = "succeeded" if success else "failed"
            self.db.execute(
                "UPDATE jobs SET status=?,updated_at=?,worker_id=NULL,lease_expires=NULL,"
                "result_json=?,log_text=?,artifact_digests_json=? WHERE job_id=?",
                (status, now, _json(result), log_text,
                 _json(artifact_digests or []), job_id),
            )
            self.db.execute("INSERT INTO job_events(job_id,kind,payload_json,created_at) VALUES(?,?,?,?)",
                            (job_id, status, _json({"worker_id": worker_id,
                                                   "result": result,
                                                   "artifacts": artifact_digests or []}), now))
            self._event("job.finished", {"job_id": job_id, "status": status,
                                         "artifacts": artifact_digests or []})
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def job(self, job_id: str) -> dict[str, Any]:
        row = self.db.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise ForgeError("unknown job")
        return {key: row[key] for key in row.keys()}

    def verify_event_chain(self) -> bool:
        previous = "0" * 64
        rows = self.db.execute("SELECT * FROM forge_events ORDER BY sequence").fetchall()
        for row in rows:
            body = _json({"event_id": row["event_id"], "kind": row["kind"],
                          "payload": json.loads(row["payload_json"]),
                          "previous_hash": previous, "created_at": row["created_at"]})
            if row["previous_hash"] != previous or row["event_hash"] != _sha(body.encode()):
                return False
            previous = row["event_hash"]
        return True
