"""Merlin's local, durable virtual Git service.

This is a content-addressed repository model, not a wrapper around GitHub.
It stores immutable blobs/commits, mutable branch refs, pull requests and an
append-only event stream in SQLite. Hashes prove byte identity, not correctness.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Mapping


class VirtualGitError(ValueError):
    pass


class VirtualRepository:
    def __init__(self, database: str | Path):
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS blobs(
              digest TEXT PRIMARY KEY, content BLOB NOT NULL, size_bytes INTEGER NOT NULL,
              created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS commits(
              commit_id TEXT PRIMARY KEY, parent1 TEXT REFERENCES commits(commit_id),
              parent2 TEXT REFERENCES commits(commit_id), tree_json TEXT NOT NULL,
              message TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS branches(
              name TEXT PRIMARY KEY, commit_id TEXT NOT NULL REFERENCES commits(commit_id),
              updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS pull_requests(
              pr_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
              source_branch TEXT NOT NULL, target_branch TEXT NOT NULL,
              base_commit TEXT NOT NULL, head_commit TEXT NOT NULL,
              status TEXT NOT NULL CHECK(status IN ('open','merged','closed')),
              merge_commit TEXT REFERENCES commits(commit_id),
              created_at REAL NOT NULL, updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS events(
              event_id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL,
              payload_json TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS events_kind_id ON events(kind,event_id);
            CREATE INDEX IF NOT EXISTS commits_parent1 ON commits(parent1);
            CREATE INDEX IF NOT EXISTS commits_parent2 ON commits(parent2);
            CREATE TRIGGER IF NOT EXISTS virtual_blobs_no_update
              BEFORE UPDATE ON blobs
              BEGIN SELECT RAISE(ABORT, 'virtual repository blobs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS virtual_blobs_no_delete
              BEFORE DELETE ON blobs
              BEGIN SELECT RAISE(ABORT, 'virtual repository blobs are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS virtual_commits_no_update
              BEFORE UPDATE ON commits
              BEGIN SELECT RAISE(ABORT, 'virtual repository commits are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS virtual_commits_no_delete
              BEFORE DELETE ON commits
              BEGIN SELECT RAISE(ABORT, 'virtual repository commits are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS virtual_events_no_update
              BEFORE UPDATE ON events
              BEGIN SELECT RAISE(ABORT, 'virtual repository events are append-only'); END;
            CREATE TRIGGER IF NOT EXISTS virtual_events_no_delete
              BEFORE DELETE ON events
              BEGIN SELECT RAISE(ABORT, 'virtual repository events are append-only'); END;
            """)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _name(value: str, label: str) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,119}", value):
            raise VirtualGitError(f"invalid {label}")
        if ".." in value.split("/") or value.endswith("/"):
            raise VirtualGitError(f"invalid {label}")
        return value

    @classmethod
    def _path(cls, value: str) -> str:
        path = cls._name(value, "file path")
        if path.startswith("/") or "\\" in path or path.startswith(".git/"):
            raise VirtualGitError("file path must be relative and traversal-free")
        return path

    def _event(self, db, kind: str, payload: Mapping[str, Any]) -> None:
        db.execute("INSERT INTO events(kind,payload_json,created_at) VALUES(?,?,?)",
                   (kind, self._canonical(dict(payload)), time.time()))

    def _put_blob(self, db, content: bytes) -> str:
        digest = sha256(content).hexdigest()
        db.execute("INSERT OR IGNORE INTO blobs VALUES(?,?,?,?)",
                   (digest, sqlite3.Binary(content), len(content), time.time()))
        return digest

    def _put_commit(self, db, tree: dict[str, str], message: str,
                    parent1: str | None, parent2: str | None = None) -> str:
        canonical_tree = dict(sorted(tree.items()))
        payload = {"tree": canonical_tree, "message": message,
                   "parent1": parent1, "parent2": parent2}
        commit_id = sha256(self._canonical(payload).encode("utf-8")).hexdigest()
        db.execute("INSERT OR IGNORE INTO commits VALUES(?,?,?,?,?,?)",
                   (commit_id, parent1, parent2, self._canonical(canonical_tree),
                    message, time.time()))
        return commit_id

    def _tree(self, db, commit_id: str) -> dict[str, str]:
        row = db.execute("SELECT tree_json FROM commits WHERE commit_id=?", (commit_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown commit: {commit_id}")
        return json.loads(row["tree_json"])

    def initialize(self, files: Mapping[str, str | bytes], branch: str = "main") -> dict[str, Any]:
        branch = self._name(branch, "branch")
        if not isinstance(files, Mapping) or not files:
            raise VirtualGitError("initial repository requires at least one file")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM branches LIMIT 1").fetchone():
                raise VirtualGitError("repository is already initialized")
            tree = {}
            for path, content in files.items():
                path = self._path(path)
                raw = content.encode("utf-8") if isinstance(content, str) else content
                if not isinstance(raw, bytes) or len(raw) > 10_000_000:
                    raise VirtualGitError("file content must be bytes/text under 10 MB")
                tree[path] = self._put_blob(db, raw)
            commit_id = self._put_commit(db, tree, "Initialize Merlin virtual repository", None)
            db.execute("INSERT INTO branches VALUES(?,?,?)", (branch, commit_id, time.time()))
            self._event(db, "repository.initialized", {"branch": branch, "commit": commit_id,
                                                        "file_count": len(tree)})
            return {"branch": branch, "commit_id": commit_id, "file_count": len(tree)}

    def branches(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT name,commit_id,updated_at FROM branches ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def create_branch(self, name: str, from_ref: str = "main") -> dict[str, Any]:
        name = self._name(name, "branch")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM branches WHERE name=?", (name,)).fetchone():
                raise VirtualGitError("branch already exists")
            source = db.execute("SELECT commit_id FROM branches WHERE name=?", (from_ref,)).fetchone()
            if source is None:
                source = db.execute("SELECT commit_id FROM commits WHERE commit_id=?", (from_ref,)).fetchone()
            if source is None:
                raise KeyError(f"unknown branch or commit: {from_ref}")
            db.execute("INSERT INTO branches VALUES(?,?,?)", (name, source["commit_id"], time.time()))
            self._event(db, "branch.created", {"branch": name, "from_ref": from_ref,
                                                "commit": source["commit_id"]})
            return {"branch": name, "commit_id": source["commit_id"]}

    def commit(self, branch: str, message: str, changes: Mapping[str, str | bytes | None]) -> dict[str, Any]:
        branch = self._name(branch, "branch")
        if not isinstance(message, str) or not message.strip() or len(message) > 500:
            raise VirtualGitError("commit message must be 1-500 characters")
        if not isinstance(changes, Mapping) or not changes or len(changes) > 500:
            raise VirtualGitError("commit requires 1-500 file changes")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            ref = db.execute("SELECT commit_id FROM branches WHERE name=?", (branch,)).fetchone()
            if ref is None:
                raise KeyError(f"unknown branch: {branch}")
            tree = self._tree(db, ref["commit_id"])
            changed = []
            for raw_path, content in changes.items():
                path = self._path(raw_path)
                if content is None:
                    tree.pop(path, None)
                else:
                    raw = content.encode("utf-8") if isinstance(content, str) else content
                    if not isinstance(raw, bytes) or len(raw) > 10_000_000:
                        raise VirtualGitError("file content must be bytes/text under 10 MB")
                    tree[path] = self._put_blob(db, raw)
                changed.append(path)
            commit_id = self._put_commit(db, tree, message, ref["commit_id"])
            updated = db.execute("UPDATE branches SET commit_id=?,updated_at=? WHERE name=? AND commit_id=?",
                       (commit_id, time.time(), branch, ref["commit_id"]))
            if updated.rowcount != 1:
                raise VirtualGitError("branch advanced concurrently; retry the commit")
            self._event(db, "commit.created", {"branch": branch, "commit": commit_id,
                                                "parent": ref["commit_id"],
                                                "paths": sorted(changed)})
            return {"branch": branch, "commit_id": commit_id,
                    "parent": ref["commit_id"], "changed_paths": sorted(changed)}

    def read_file(self, ref: str, path: str) -> bytes:
        path = self._path(path)
        with closing(self._connect()) as db:
            branch = db.execute("SELECT commit_id FROM branches WHERE name=?", (ref,)).fetchone()
            commit_id = branch["commit_id"] if branch else ref
            tree = self._tree(db, commit_id)
            digest = tree.get(path)
            if digest is None:
                raise KeyError(path)
            row = db.execute("SELECT content FROM blobs WHERE digest=?", (digest,)).fetchone()
            if row is None or sha256(row["content"]).hexdigest() != digest:
                raise RuntimeError("virtual repository blob integrity failure")
            return bytes(row["content"])

    def open_pull_request(self, source_branch: str, target_branch: str = "main",
                          title: str = "Untitled change") -> dict[str, Any]:
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise VirtualGitError("pull request title must be 1-200 characters")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if source_branch == target_branch:
                raise VirtualGitError("source and target branches must differ")
            source = db.execute("SELECT commit_id FROM branches WHERE name=?", (source_branch,)).fetchone()
            target = db.execute("SELECT commit_id FROM branches WHERE name=?", (target_branch,)).fetchone()
            if source is None or target is None:
                raise KeyError("source and target branches must exist")
            cursor = db.execute("""INSERT INTO pull_requests
                (title,source_branch,target_branch,base_commit,head_commit,status,created_at,updated_at)
                VALUES(?,?,?,?,?,'open',?,?)""",
                (title.strip(), source_branch, target_branch, target["commit_id"],
                 source["commit_id"], time.time(), time.time()))
            pr_id = cursor.lastrowid
            self._event(db, "pull_request.opened", {"pr_id": pr_id, "source": source_branch,
                "target": target_branch, "base": target["commit_id"], "head": source["commit_id"]})
            return {"pr_id": pr_id, "title": title.strip(), "source_branch": source_branch,
                    "target_branch": target_branch, "base_commit": target["commit_id"],
                    "head_commit": source["commit_id"], "status": "open"}

    def _parents(self, db, commit_id: str) -> tuple[str | None, str | None]:
        row = db.execute("SELECT parent1,parent2 FROM commits WHERE commit_id=?", (commit_id,)).fetchone()
        if row is None:
            raise KeyError(commit_id)
        return row["parent1"], row["parent2"]

    def _ancestors(self, db, start: str) -> dict[str, int]:
        distances, queue = {}, [(start, 0)]
        while queue:
            current, distance = queue.pop(0)
            if current in distances and distances[current] <= distance:
                continue
            distances[current] = distance
            for parent in self._parents(db, current):
                if parent is not None:
                    queue.append((parent, distance + 1))
        return distances

    def merge_pull_request(self, pr_id: int) -> dict[str, Any]:
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            pr = db.execute("SELECT * FROM pull_requests WHERE pr_id=?", (pr_id,)).fetchone()
            if pr is None:
                raise KeyError(f"unknown pull request: {pr_id}")
            if pr["status"] != "open":
                raise VirtualGitError("pull request is not open")
            source = db.execute("SELECT commit_id FROM branches WHERE name=?", (pr["source_branch"],)).fetchone()
            target = db.execute("SELECT commit_id FROM branches WHERE name=?", (pr["target_branch"],)).fetchone()
            if source is None or target is None:
                raise VirtualGitError("pull request branch no longer exists")
            source_head, target_head = source["commit_id"], target["commit_id"]
            source_ancestors, target_ancestors = self._ancestors(db, source_head), self._ancestors(db, target_head)
            common = set(source_ancestors) & set(target_ancestors)
            if not common:
                raise VirtualGitError("branches have no common ancestor")
            base_id = min(common, key=lambda item: (source_ancestors[item] + target_ancestors[item],
                                                     max(source_ancestors[item], target_ancestors[item]), item))
            base_tree, source_tree, target_tree = (self._tree(db, item) for item in
                                                   (base_id, source_head, target_head))
            merged = {}
            conflicts = []
            for path in sorted(set(base_tree) | set(source_tree) | set(target_tree)):
                base_value, source_value, target_value = (tree.get(path) for tree in
                                                           (base_tree, source_tree, target_tree))
                if source_value == target_value:
                    value = source_value
                elif source_value == base_value:
                    value = target_value
                elif target_value == base_value:
                    value = source_value
                else:
                    conflicts.append(path)
                    continue
                if value is not None:
                    merged[path] = value
            if conflicts:
                self._event(db, "pull_request.merge_conflict", {"pr_id": pr_id,
                    "base": base_id, "source": source_head, "target": target_head,
                    "conflicts": conflicts})
                return {"pr_id": pr_id, "status": "conflict", "conflicts": conflicts,
                        "base_commit": base_id, "head_commit": source_head,
                        "target_commit": target_head}
            merge_id = self._put_commit(db, merged, f"Merge virtual PR #{pr_id}",
                                        target_head, source_head)
            updated = db.execute("UPDATE branches SET commit_id=?,updated_at=? WHERE name=? AND commit_id=?",
                       (merge_id, time.time(), pr["target_branch"], target_head))
            if updated.rowcount != 1:
                raise VirtualGitError("target branch advanced concurrently; retry the merge")
            db.execute("UPDATE pull_requests SET status='merged',merge_commit=?,updated_at=? WHERE pr_id=?",
                       (merge_id, time.time(), pr_id))
            self._event(db, "pull_request.merged", {"pr_id": pr_id, "merge_commit": merge_id,
                "target": pr["target_branch"], "source": pr["source_branch"]})
            return {"pr_id": pr_id, "status": "merged", "merge_commit": merge_id,
                    "target_branch": pr["target_branch"], "source_head": source_head}

    def rollback_branch(self, branch: str, commit_id: str) -> dict[str, Any]:
        branch = self._name(branch, "branch")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM branches WHERE name=?", (branch,)).fetchone():
                raise KeyError(branch)
            self._tree(db, commit_id)
            old = db.execute("SELECT commit_id FROM branches WHERE name=?", (branch,)).fetchone()["commit_id"]
            db.execute("UPDATE branches SET commit_id=?,updated_at=? WHERE name=?",
                       (commit_id, time.time(), branch))
            self._event(db, "branch.rollback", {"branch": branch, "from": old, "to": commit_id})
            return {"branch": branch, "previous_commit": old, "commit_id": commit_id}

    def pull_requests(self, status: str | None = None) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            if status is None:
                rows = db.execute("SELECT * FROM pull_requests ORDER BY pr_id DESC").fetchall()
            else:
                rows = db.execute("SELECT * FROM pull_requests WHERE status=? ORDER BY pr_id DESC",
                                  (status,)).fetchall()
        return [dict(row) for row in rows]

    def events(self, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise VirtualGitError("event limit must be between 1 and 1000")
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM events ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()
        return [{"event_id": row["event_id"], "kind": row["kind"],
                 "payload": json.loads(row["payload_json"]), "created_at": row["created_at"]}
                for row in rows]
