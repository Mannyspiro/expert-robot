"""Merlin's local, durable virtual Git service.

This is a content-addressed repository model, not a wrapper around GitHub.
It stores immutable blobs/commits, mutable branch refs, pull requests and an
append-only event stream in SQLite. Hashes prove byte identity, not correctness.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sqlite3
import time
import uuid
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
            CREATE TABLE IF NOT EXISTS branch_policies(
              branch TEXT PRIMARY KEY, required_checks_json TEXT NOT NULL,
              updated_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS check_results(
              check_id INTEGER PRIMARY KEY AUTOINCREMENT,
              commit_id TEXT NOT NULL REFERENCES commits(commit_id),
              check_name TEXT NOT NULL, conclusion TEXT NOT NULL
                CHECK(conclusion IN ('success','failure','cancelled')),
              run_id TEXT NOT NULL, runner_id TEXT NOT NULL,
              log_digest TEXT NOT NULL REFERENCES blobs(digest),
              result_json TEXT NOT NULL, recorded_at REAL NOT NULL,
              UNIQUE(run_id, check_name));
            CREATE INDEX IF NOT EXISTS check_results_commit_name
              ON check_results(commit_id,check_name,recorded_at);
            CREATE INDEX IF NOT EXISTS events_kind_id ON events(kind,event_id);
            CREATE INDEX IF NOT EXISTS commits_parent1 ON commits(parent1);
            CREATE INDEX IF NOT EXISTS commits_parent2 ON commits(parent2);
            CREATE TABLE IF NOT EXISTS virtual_jobs(
              job_id TEXT PRIMARY KEY,
              commit_id TEXT NOT NULL REFERENCES commits(commit_id),
              job_type TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled')),
              attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL DEFAULT 2,
              runner_id TEXT,
              lease_token_hash TEXT,
              lease_expires_at REAL,
              result_json TEXT,
              log_digest TEXT REFERENCES blobs(digest),
              created_at REAL NOT NULL,
              updated_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS virtual_jobs_queue
              ON virtual_jobs(status,created_at,job_id);
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
            CREATE TRIGGER IF NOT EXISTS virtual_check_results_no_update
              BEFORE UPDATE ON check_results
              BEGIN SELECT RAISE(ABORT, 'virtual repository check results are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS virtual_check_results_no_delete
              BEFORE DELETE ON check_results
              BEGIN SELECT RAISE(ABORT, 'virtual repository check results are immutable'); END;
            """)
            if db.execute("SELECT 1 FROM branches WHERE name='main'").fetchone():
                default_checks = self._canonical([
                    "python.compile", "python.unified_tests", "hud.javascript_syntax",
                ])
                db.execute("INSERT OR IGNORE INTO branch_policies VALUES(?,?,?)",
                           ("main", default_checks, time.time()))

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
            if branch == "main":
                required = ["python.compile", "python.unified_tests", "hud.javascript_syntax"]
                db.execute("INSERT INTO branch_policies VALUES(?,?,?)",
                           (branch, self._canonical(required), time.time()))
            self._event(db, "repository.initialized", {"branch": branch, "commit": commit_id,
                                                        "file_count": len(tree)})
            return {"branch": branch, "commit_id": commit_id, "file_count": len(tree)}

    def integrity_report(self) -> dict[str, Any]:
        """Verify SQLite structure, foreign keys, blob hashes and commit identities."""
        problems: list[str] = []
        with closing(self._connect()) as db:
            integrity = [row[0] for row in db.execute("PRAGMA integrity_check").fetchall()]
            if integrity != ["ok"]:
                problems.extend("sqlite:" + str(item) for item in integrity)
            foreign_keys = [tuple(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()]
            if foreign_keys:
                problems.append("foreign_key_violations")
            blob_rows = db.execute("SELECT digest,content,size_bytes FROM blobs").fetchall()
            for row in blob_rows:
                raw = bytes(row["content"])
                if sha256(raw).hexdigest() != row["digest"] or len(raw) != row["size_bytes"]:
                    problems.append("blob:" + row["digest"])
            commits = db.execute("""SELECT commit_id,parent1,parent2,tree_json,message
                FROM commits""").fetchall()
            for row in commits:
                try:
                    tree = json.loads(row["tree_json"])
                    if not isinstance(tree, dict) or any(
                        not isinstance(path, str) or not isinstance(digest, str)
                        for path, digest in tree.items()
                    ):
                        raise ValueError("commit tree must map text paths to text digests")
                    payload = {"tree": dict(sorted(tree.items())), "message": row["message"],
                               "parent1": row["parent1"], "parent2": row["parent2"]}
                    expected = sha256(self._canonical(payload).encode("utf-8")).hexdigest()
                    if expected != row["commit_id"]:
                        problems.append("commit:" + row["commit_id"])
                    for path, digest in tree.items():
                        if not db.execute("SELECT 1 FROM blobs WHERE digest=?", (digest,)).fetchone():
                            problems.append("missing_blob:" + str(path))
                except (AttributeError, TypeError, ValueError):
                    problems.append("invalid_commit_tree:" + row["commit_id"])
            counts = {
                "blobs": db.execute("SELECT COUNT(*) FROM blobs").fetchone()[0],
                "commits": db.execute("SELECT COUNT(*) FROM commits").fetchone()[0],
                "branches": db.execute("SELECT COUNT(*) FROM branches").fetchone()[0],
                "pull_requests": db.execute("SELECT COUNT(*) FROM pull_requests").fetchone()[0],
            }
        return {"ok": not problems, "problems": problems, "counts": counts,
                "integrity_check": integrity, "foreign_key_violations": foreign_keys}

    def backup_to(self, destination: str | Path) -> dict[str, Any]:
        """Create a transactionally consistent SQLite backup without overwriting files."""
        target = Path(destination)
        if target.resolve() == self.path.resolve():
            raise VirtualGitError("backup destination must differ from the live repository")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise VirtualGitError("backup destination already exists")
        temporary = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with closing(self._connect()) as source, closing(sqlite3.connect(temporary)) as backup:
                source.backup(backup)
            report = VirtualRepository(temporary).integrity_report()
            if not report["ok"]:
                raise RuntimeError("backup integrity verification failed: " + repr(report["problems"]))
            # A same-directory hard link publishes the verified backup atomically
            # and fails rather than replacing a destination created concurrently.
            os.link(temporary, target)
            return {"path": str(target.resolve()), "integrity": report}
        finally:
            temporary.unlink(missing_ok=True)
            Path(str(temporary) + "-wal").unlink(missing_ok=True)
            Path(str(temporary) + "-shm").unlink(missing_ok=True)

    def export_commit(self, commit_id: str, destination: str | Path,
                     *, max_total_bytes: int = 100_000_000) -> dict[str, Any]:
        """Materialize a verified commit into a new, isolated workspace directory."""
        target = Path(destination)
        if target.exists():
            raise VirtualGitError("workspace destination already exists")
        if isinstance(max_total_bytes, bool) or not isinstance(max_total_bytes, int) or not 1 <= max_total_bytes <= 500_000_000:
            raise VirtualGitError("workspace byte limit is outside the allowed range")
        with closing(self._connect()) as db:
            tree = self._tree(db, commit_id)
            if not isinstance(tree, dict):
                raise RuntimeError("commit tree is not a path-to-digest object")
            files: list[tuple[str, str, bytes]] = []
            total_bytes = 0
            for path, digest in sorted(tree.items()):
                safe_path = self._path(path)
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise RuntimeError("commit tree contains an invalid blob digest: " + safe_path)
                row = db.execute("SELECT content,size_bytes FROM blobs WHERE digest=?", (digest,)).fetchone()
                if row is None:
                    raise RuntimeError("commit references a missing blob: " + safe_path)
                content = bytes(row["content"])
                if sha256(content).hexdigest() != digest or len(content) != row["size_bytes"]:
                    raise RuntimeError("commit blob integrity failure: " + safe_path)
                total_bytes += len(content)
                if total_bytes > max_total_bytes:
                    raise VirtualGitError("commit exceeds the workspace materialization byte limit")
                files.append((safe_path, digest, content))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.mkdir(parents=False, exist_ok=False)
        try:
            manifest_files = []
            for path, digest, content in files:
                output = target / Path(*path.split("/"))
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(content)
                manifest_files.append({"path": path, "sha256": digest, "size_bytes": len(content)})
            return {
                "commit_id": commit_id,
                "workspace": str(target.resolve()),
                "file_count": len(manifest_files),
                "total_bytes": total_bytes,
                "tree_sha256": sha256(self._canonical(tree).encode("utf-8")).hexdigest(),
                "files": manifest_files,
            }
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

    def branches(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT name,commit_id,updated_at FROM branches ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    CHECK_NAMES = {"python.compile", "python.unified_tests", "hud.javascript_syntax"}

    def required_checks(self, branch: str) -> list[str]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT required_checks_json FROM branch_policies WHERE branch=?",
                             (branch,)).fetchone()
        return json.loads(row["required_checks_json"]) if row else []

    def set_branch_policy(self, branch: str, required_checks: list[str]) -> dict[str, Any]:
        branch = self._name(branch, "branch")
        if (not isinstance(required_checks, list) or len(required_checks) > len(self.CHECK_NAMES)
                or any(not isinstance(name, str) for name in required_checks)):
            raise VirtualGitError("required checks must be a bounded list of names")
        if len(set(required_checks)) != len(required_checks) or any(
            name not in self.CHECK_NAMES for name in required_checks
        ):
            raise VirtualGitError("unknown or duplicate required check")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM branches WHERE name=?", (branch,)).fetchone():
                raise KeyError(branch)
            encoded = self._canonical(required_checks)
            db.execute("""INSERT INTO branch_policies(branch,required_checks_json,updated_at)
                VALUES(?,?,?) ON CONFLICT(branch) DO UPDATE SET
                required_checks_json=excluded.required_checks_json,updated_at=excluded.updated_at""",
                (branch, encoded, time.time()))
            self._event(db, "branch.policy_updated", {"branch": branch,
                                                        "required_checks": required_checks})
        return {"branch": branch, "required_checks": required_checks}

    def record_check_result(self, commit_id: str, check_name: str, conclusion: str,
                            run_id: str, runner_id: str, log: str) -> dict[str, Any]:
        if not isinstance(check_name, str) or check_name not in self.CHECK_NAMES:
            raise VirtualGitError("unknown check name")
        if not isinstance(conclusion, str) or conclusion not in {"success", "failure", "cancelled"}:
            raise VirtualGitError("invalid check conclusion")
        if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 200:
            raise VirtualGitError("run_id must be 1-200 characters")
        if not isinstance(runner_id, str) or not runner_id.strip() or len(runner_id) > 200:
            raise VirtualGitError("runner_id must be 1-200 characters")
        if not isinstance(log, str) or len(log.encode("utf-8")) > 5_000_000:
            raise VirtualGitError("check log must be UTF-8 text under 5 MB")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._tree(db, commit_id)
            log_digest = self._put_blob(db, log.encode("utf-8"))
            existing = db.execute("SELECT * FROM check_results WHERE run_id=? AND check_name=?",
                                  (run_id, check_name)).fetchone()
            if existing is not None:
                if (existing["commit_id"], existing["conclusion"], existing["runner_id"],
                    existing["log_digest"]) != (commit_id, conclusion, runner_id, log_digest):
                    raise VirtualGitError("run_id already records a different check result")
                metadata = json.loads(existing["result_json"])
                return {"check_id": existing["check_id"], "commit_id": commit_id,
                        "check_name": check_name, "conclusion": conclusion,
                        "log_sha256": log_digest,
                        "verification_status": metadata.get("verification_status", "UNVERIFIED"),
                        "promotion_authorized": metadata.get("promotion_authorized") is True,
                        "idempotent_replay": True}
            result = {"commit_id": commit_id, "check_name": check_name,
                      "conclusion": conclusion, "run_id": run_id, "runner_id": runner_id,
                      "log_sha256": log_digest, "verification_status": "UNVERIFIED",
                      "promotion_authorized": False}
            cursor = db.execute("""INSERT INTO check_results
                (commit_id,check_name,conclusion,run_id,runner_id,log_digest,result_json,recorded_at)
                VALUES(?,?,?,?,?,?,?,?)""",
                (commit_id, check_name, conclusion, run_id, runner_id, log_digest,
                 self._canonical(result), time.time()))
            check_id = cursor.lastrowid
            self._event(db, "check.recorded", {"check_id": check_id, **result})
            return {"check_id": check_id, **result, "idempotent_replay": False}

    def check_results(self, commit_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT check_id,commit_id,check_name,conclusion,run_id,
                runner_id,log_digest,result_json,recorded_at FROM check_results
                WHERE commit_id=? ORDER BY recorded_at,check_id""", (commit_id,)).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            try:
                metadata = json.loads(item.pop("result_json"))
            except (TypeError, ValueError):
                metadata = {}
            item["verification_status"] = metadata.get("verification_status", "UNVERIFIED")
            item["promotion_authorized"] = metadata.get("promotion_authorized") is True
            results.append(item)
        return results

    def read_check_log(self, check_id: int) -> bytes:
        with closing(self._connect()) as db:
            row = db.execute("""SELECT b.content,cr.log_digest FROM check_results cr
                JOIN blobs b ON b.digest=cr.log_digest WHERE cr.check_id=?""",
                (check_id,)).fetchone()
        if row is None:
            raise KeyError(f"unknown check result: {check_id}")
        content = bytes(row["content"])
        if sha256(content).hexdigest() != row["log_digest"]:
            raise RuntimeError("virtual CI log integrity failure")
        return content

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
            policy = db.execute("SELECT required_checks_json FROM branch_policies WHERE branch=?",
                                (pr["target_branch"],)).fetchone()
            required = json.loads(policy["required_checks_json"]) if policy else []
            missing_checks, failed_checks, unverified_checks = [], [], []
            for check_name in required:
                result = db.execute("""SELECT conclusion,result_json FROM check_results
                    WHERE commit_id=? AND check_name=?
                    ORDER BY recorded_at DESC,check_id DESC LIMIT 1""",
                    (source_head, check_name)).fetchone()
                if result is None:
                    missing_checks.append(check_name)
                    continue
                if result["conclusion"] != "success":
                    failed_checks.append({"check": check_name, "conclusion": result["conclusion"]})
                    continue
                try:
                    metadata = json.loads(result["result_json"])
                except (TypeError, ValueError):
                    metadata = {}
                if not isinstance(metadata, Mapping):
                    metadata = {}
                if (metadata.get("verification_status") != "VERIFIED"
                        or metadata.get("promotion_authorized") is not True):
                    unverified_checks.append(check_name)
            if missing_checks or failed_checks or unverified_checks:
                self._event(db, "pull_request.merge_blocked", {"pr_id": pr_id,
                    "source_head": source_head, "target": pr["target_branch"],
                    "missing_checks": missing_checks, "failed_checks": failed_checks,
                    "unverified_checks": unverified_checks})
                return {"pr_id": pr_id, "status": "blocked", "source_head": source_head,
                        "missing_checks": missing_checks, "failed_checks": failed_checks,
                        "unverified_checks": unverified_checks, "required_checks": required}
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

    def rebase_branch(self, branch: str, onto_ref: str = "main") -> dict[str, Any]:
        """Replay a linear branch delta onto another branch/commit; conflicts never move refs."""
        branch = self._name(branch, "branch")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            source_row = db.execute("SELECT commit_id FROM branches WHERE name=?", (branch,)).fetchone()
            if source_row is None:
                raise KeyError(f"unknown branch: {branch}")
            target_row = db.execute("SELECT commit_id FROM branches WHERE name=?", (onto_ref,)).fetchone()
            if target_row is None:
                target_row = db.execute("SELECT commit_id FROM commits WHERE commit_id=?", (onto_ref,)).fetchone()
            if target_row is None:
                raise KeyError(f"unknown branch or commit: {onto_ref}")
            source_head, target_head = source_row["commit_id"], target_row["commit_id"]
            if source_head == target_head:
                return {"branch": branch, "status": "up_to_date", "commit_id": source_head}
            source_ancestors = self._ancestors(db, source_head)
            target_ancestors = self._ancestors(db, target_head)
            if target_head in source_ancestors:
                return {"branch": branch, "status": "up_to_date", "commit_id": source_head}
            common = set(source_ancestors) & set(target_ancestors)
            if not common:
                raise VirtualGitError("branches have no common ancestor")
            base_id = min(common, key=lambda item: (
                source_ancestors[item] + target_ancestors[item],
                max(source_ancestors[item], target_ancestors[item]), item))
            replay = []
            cursor = source_head
            while cursor != base_id:
                row = db.execute("SELECT parent1,parent2,message FROM commits WHERE commit_id=?",
                                 (cursor,)).fetchone()
                if row is None or row["parent1"] is None:
                    raise VirtualGitError("cannot determine linear commits to rebase")
                if row["parent2"] is not None:
                    raise VirtualGitError("rebase of merge commits is not supported")
                replay.append((cursor, row["parent1"], row["message"]))
                cursor = row["parent1"]
            replay.reverse()
            rebased_tree = self._tree(db, target_head)
            planned = []
            for old_commit, old_parent, message in replay:
                parent_tree = self._tree(db, old_parent)
                old_tree = self._tree(db, old_commit)
                next_tree = dict(rebased_tree)
                conflicts = []
                for logical_path in sorted(set(parent_tree) | set(old_tree) | set(rebased_tree)):
                    before = parent_tree.get(logical_path)
                    desired = old_tree.get(logical_path)
                    current = rebased_tree.get(logical_path)
                    if desired == before:
                        continue
                    if current == before or current == desired:
                        if desired is None:
                            next_tree.pop(logical_path, None)
                        else:
                            next_tree[logical_path] = desired
                    else:
                        conflicts.append(logical_path)
                if conflicts:
                    self._event(db, "branch.rebase_conflict", {
                        "branch": branch, "onto": onto_ref, "base": base_id,
                        "source_head": source_head, "target_head": target_head,
                        "conflicts": conflicts})
                    return {"branch": branch, "status": "conflict",
                            "conflicts": conflicts, "base_commit": base_id,
                            "source_head": source_head, "target_head": target_head}
                planned.append((next_tree, message))
                rebased_tree = next_tree
            new_head = target_head
            for tree, message in planned:
                new_head = self._put_commit(db, tree, message, new_head)
            updated = db.execute(
                "UPDATE branches SET commit_id=?,updated_at=? WHERE name=? AND commit_id=?",
                (new_head, time.time(), branch, source_head))
            if updated.rowcount != 1:
                raise VirtualGitError("branch advanced concurrently; retry the rebase")
            self._event(db, "branch.rebased", {"branch": branch, "onto": onto_ref,
                "old_head": source_head, "new_head": new_head, "base_commit": base_id,
                "replayed_commits": len(planned)})
            return {"branch": branch, "status": "rebased", "previous_head": source_head,
                    "commit_id": new_head, "base_commit": base_id,
                    "replayed_commits": len(planned)}

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
        query = """SELECT p.*,s.commit_id AS current_head_commit,
                   t.commit_id AS current_target_commit
                   FROM pull_requests p
                   LEFT JOIN branches s ON s.name=p.source_branch
                   LEFT JOIN branches t ON t.name=p.target_branch"""
        with closing(self._connect()) as db:
            if status is None:
                rows = db.execute(query + " ORDER BY p.pr_id DESC").fetchall()
            else:
                rows = db.execute(query + " WHERE p.status=? ORDER BY p.pr_id DESC",
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
