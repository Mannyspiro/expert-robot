#!/usr/bin/env python3
"""Idempotent SQLite registration for independently validated Merlin manifests."""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SHA256 = re.compile(r"^[0-9a-f]{64}$")
class RegistryError(Exception): pass

def manifest_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()

def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise RegistryError("Artifact path must be a non-empty string")
    normalized = value.replace("\\", "/")
    if normalized.startswith("/"): raise RegistryError("Unsafe absolute artifact path")
    parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise RegistryError("Unsafe artifact path component")
    if ":" in parts[0] or parts[0].startswith("~"):
        raise RegistryError("Drive or home-prefixed artifact path rejected")
    parsed = PurePosixPath(normalized)
    if parsed.is_absolute() or str(parsed) != normalized:
        raise RegistryError("Non-canonical artifact path")
    return normalized

def validate_manifest(data: dict) -> None:
    if not isinstance(data, dict) or data.get("manifest_version") != "1.0":
        raise RegistryError("Unsupported or malformed manifest")
    archive = data.get("archive")
    if not isinstance(archive, dict): raise RegistryError("Missing archive metadata")
    archive_sha = archive.get("sha256")
    if not isinstance(archive_sha, str) or not SHA256.fullmatch(archive_sha):
        raise RegistryError("Invalid archive SHA-256")
    if data.get("intake_id") != "sha256:" + archive_sha:
        raise RegistryError("intake_id does not match archive digest")
    filename = archive.get("filename")
    if not isinstance(filename, str) or not filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise RegistryError("Invalid archive filename")
    archive_size = archive.get("size_bytes")
    if not isinstance(archive_size, int) or isinstance(archive_size, bool) or archive_size < 0:
        raise RegistryError("Invalid archive size")
    files = data.get("files")
    if not isinstance(files, list): raise RegistryError("files must be an array")
    count = data.get("file_count")
    if not isinstance(count, int) or isinstance(count, bool) or count != len(files):
        raise RegistryError("file_count does not match files array")
    seen, total = set(), 0
    for item in files:
        if not isinstance(item, dict): raise RegistryError("Invalid file record")
        path = _safe_relative_path(item.get("path"))
        digest, size, category = item.get("sha256"), item.get("size_bytes"), item.get("classification")
        if path in seen: raise RegistryError("Duplicate normalized artifact path")
        seen.add(path)
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise RegistryError("Invalid artifact SHA-256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise RegistryError("Invalid artifact size")
        if not isinstance(category, str) or not category.strip():
            raise RegistryError("Invalid artifact classification")
        total += size
    declared_total = data.get("total_uncompressed_bytes")
    if not isinstance(declared_total, int) or isinstance(declared_total, bool) or declared_total != total:
        raise RegistryError("total_uncompressed_bytes does not match files")

def register_manifest(manifest_path: Path, database_path: Path) -> dict:
    manifest_path = manifest_path.resolve(strict=True); database_path = database_path.resolve()
    data = json.loads(manifest_path.read_text(encoding="utf-8")); validate_manifest(data)
    digest = manifest_digest(manifest_path); database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript("""
          CREATE TABLE IF NOT EXISTS intakes (
            intake_id TEXT PRIMARY KEY, archive_sha256 TEXT NOT NULL,
            archive_filename TEXT NOT NULL, archive_size_bytes INTEGER NOT NULL,
            manifest_sha256 TEXT NOT NULL, registered_at TEXT NOT NULL,
            file_count INTEGER NOT NULL, total_uncompressed_bytes INTEGER NOT NULL
          );
          CREATE TABLE IF NOT EXISTS artifacts (
            intake_id TEXT NOT NULL REFERENCES intakes(intake_id) ON DELETE CASCADE,
            path TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
            classification TEXT NOT NULL, PRIMARY KEY (intake_id, path)
          );
          CREATE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256);
          CREATE INDEX IF NOT EXISTS idx_artifacts_classification ON artifacts(classification);
        """)
        existing = connection.execute("SELECT manifest_sha256 FROM intakes WHERE intake_id=?",
                                       (data["intake_id"],)).fetchone()
        if existing:
            if existing[0] != digest: raise RegistryError("Same intake_id already registered with a different manifest")
            return {"status":"already_registered","intake_id":data["intake_id"],
                    "file_count":data["file_count"],"database":str(database_path)}
        with connection:
            connection.execute("INSERT INTO intakes VALUES (?,?,?,?,?,?,?,?)",
              (data["intake_id"],data["archive"]["sha256"],data["archive"]["filename"],
               data["archive"]["size_bytes"],digest,datetime.now(timezone.utc).isoformat(),
               data["file_count"],data["total_uncompressed_bytes"]))
            connection.executemany("INSERT INTO artifacts VALUES (?,?,?,?,?)",
              [(data["intake_id"],_safe_relative_path(x["path"]),x["sha256"],x["size_bytes"],x["classification"])
               for x in data["files"]])
        return {"status":"registered","intake_id":data["intake_id"],"file_count":data["file_count"],
                "database":str(database_path)}
    finally: connection.close()

def main():
    parser=argparse.ArgumentParser(description="Register a Merlin intake manifest in a local SQLite project inventory.")
    parser.add_argument("manifest",type=Path); parser.add_argument("--database",type=Path,default=Path("merlin-registry.sqlite3"))
    args=parser.parse_args()
    try:
        print(json.dumps(register_manifest(args.manifest,args.database),indent=2)); return 0
    except (OSError,ValueError,RegistryError,sqlite3.Error) as exc:
        print(json.dumps({"status":"rejected","error":str(exc)},indent=2),file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
