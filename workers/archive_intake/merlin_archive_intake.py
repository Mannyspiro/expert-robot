#!/usr/bin/env python3
"""Safe, non-executing ZIP intake for Merlin."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, stat, sys, tempfile, zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

@dataclass(frozen=True)
class IntakeLimits:
    max_files: int = 5000
    max_total_uncompressed: int = 512 * 1024 * 1024
    max_member_uncompressed: int = 128 * 1024 * 1024
    max_compression_ratio: float = 200.0
    max_path_length: int = 240

class IntakeError(Exception):
    pass

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def classify(path: str) -> str:
    suffix = Path(path).suffix.lower()
    mapping = {
        ".lean":"formal_proof", ".tex":"research_document", ".pdf":"document",
        ".md":"documentation", ".rst":"documentation", ".py":"source_code",
        ".js":"source_code", ".ts":"source_code", ".jsx":"source_code",
        ".tsx":"source_code", ".json":"structured_data", ".yaml":"configuration",
        ".yml":"configuration", ".toml":"configuration", ".xml":"structured_data",
        ".xaml":"automation_workflow", ".step":"cad_model", ".stp":"cad_model",
        ".iges":"cad_model", ".igs":"cad_model", ".stl":"mesh_model",
        ".obj":"mesh_model", ".gcode":"manufacturing_data", ".csv":"dataset",
        ".tsv":"dataset", ".xlsx":"spreadsheet", ".ods":"spreadsheet",
        ".png":"image", ".jpg":"image", ".jpeg":"image", ".webp":"image",
        ".mp4":"video", ".mov":"video"
    }
    return mapping.get(suffix, "unclassified")

def safe_member_name(raw: str, limits: IntakeLimits) -> str:
    if "\x00" in raw:
        raise IntakeError("NUL byte in member name")
    name = raw.replace("\\", "/")
    if len(name) > limits.max_path_length:
        raise IntakeError("Member path too long")
    if name.startswith("/") or name.startswith("//"):
        raise IntakeError("Absolute path rejected: " + raw)
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts[:-1]):
        raise IntakeError("Unsafe path component rejected: " + raw)
    if parts and (":" in parts[0] or parts[0].startswith("~")):
        raise IntakeError("Drive or home path rejected: " + raw)
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or str(path) in ("", "."):
        raise IntakeError("Unsafe archive path rejected: " + raw)
    return str(path)

def validate_archive(zf: zipfile.ZipFile, limits: IntakeLimits):
    infos = zf.infolist()
    if len(infos) > limits.max_files:
        raise IntakeError("Archive entry count exceeds limit")
    seen, total, accepted = set(), 0, []
    for info in infos:
        name = safe_member_name(info.filename, limits)
        if name in seen:
            raise IntakeError("Duplicate normalized path: " + name)
        seen.add(name)
        if info.flag_bits & 1:
            raise IntakeError("Encrypted member rejected: " + name)
        mode = (info.external_attr >> 16) & 0xFFFF
        if stat.S_ISLNK(mode):
            raise IntakeError("Symbolic link rejected: " + name)
        if mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise IntakeError("Special filesystem entry rejected: " + name)
        if info.file_size < 0 or info.compress_size < 0:
            raise IntakeError("Invalid size metadata: " + name)
        if not info.is_dir():
            if info.file_size > limits.max_member_uncompressed:
                raise IntakeError("Member size exceeds limit: " + name)
            total += info.file_size
            if total > limits.max_total_uncompressed:
                raise IntakeError("Total expanded size exceeds limit")
            if info.file_size and info.compress_size == 0:
                raise IntakeError("Invalid compression metadata: " + name)
            if info.compress_size and info.file_size / info.compress_size > limits.max_compression_ratio:
                raise IntakeError("Compression ratio exceeds policy: " + name)
        accepted.append((info, name))
    return accepted

def intake_archive(archive_path: Path, destination: Path, limits=None) -> dict:
    limits = limits or IntakeLimits()
    archive_path = archive_path.resolve(strict=True)
    destination = destination.resolve()
    if not archive_path.is_file():
        raise IntakeError("Input must be a regular archive file")
    if destination.exists():
        raise IntakeError("Destination already exists: " + str(destination))
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive_hash = sha256_file(archive_path)
    staging = Path(tempfile.mkdtemp(prefix=".merlin-intake-", dir=destination.parent))
    started = datetime.now(timezone.utc).isoformat()
    records = []
    try:
        with zipfile.ZipFile(archive_path, "r") as zf:
            members = validate_archive(zf, limits)
            for info, name in members:
                target = staging.joinpath(*PurePosixPath(name).parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, written = hashlib.sha256(), 0
                with zf.open(info, "r") as source, target.open("xb") as sink:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > limits.max_member_uncompressed:
                            raise IntakeError("Actual expanded size exceeds limit: " + name)
                        digest.update(chunk)
                        sink.write(chunk)
                if written != info.file_size:
                    raise IntakeError("Expanded size mismatch: " + name)
                records.append({"path":name,"sha256":digest.hexdigest(),
                                "size_bytes":written,"classification":classify(name)})
        manifest = {
            "manifest_version":"1.0", "intake_id":"sha256:" + archive_hash,
            "archive":{"filename":archive_path.name,"sha256":archive_hash,
                       "size_bytes":archive_path.stat().st_size},
            "started_at":started,"finished_at":datetime.now(timezone.utc).isoformat(),
            "policy":asdict(limits),"execution_policy":"contents_inspected_only_never_executed",
            "file_count":len(records),
            "total_uncompressed_bytes":sum(x["size_bytes"] for x in records),
            "files":sorted(records,key=lambda x:x["path"].casefold())
        }
        (staging / "merlin-intake-manifest.json").write_text(
            json.dumps(manifest,indent=2,sort_keys=True) + "\n",encoding="utf-8")
        os.replace(staging,destination)
        return manifest
    except Exception:
        shutil.rmtree(staging,ignore_errors=True)
        raise

def main():
    parser = argparse.ArgumentParser(description="Safely inspect a ZIP; never executes contents.")
    parser.add_argument("archive",type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--max-files",type=int,default=IntakeLimits.max_files)
    parser.add_argument("--max-total-mb",type=int,default=512)
    args = parser.parse_args()
    try:
        limits = IntakeLimits(max_files=args.max_files,
                              max_total_uncompressed=args.max_total_mb*1024*1024)
        manifest = intake_archive(args.archive,args.output,limits)
        print(json.dumps({"status":"passed","intake_id":manifest["intake_id"],
                          "file_count":manifest["file_count"],
                          "total_uncompressed_bytes":manifest["total_uncompressed_bytes"],
                          "manifest":str(args.output/"merlin-intake-manifest.json")},indent=2))
        return 0
    except (IntakeError,OSError,zipfile.BadZipFile,RuntimeError) as exc:
        print(json.dumps({"status":"quarantined","error":str(exc)},indent=2),file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
