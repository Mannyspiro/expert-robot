"""Merkle-checked installation and local-only startup of the real Merlin Studio source.

This is not an AI inference engine. The APK boots original Studio with its offline
commands. Potentially dangerous Python/desktop/network tools are explicitly blocked.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import tempfile
import threading
import zipfile

ROOT = "Merlin_Studio/"
LOCK = threading.RLock()
RUNNING = None
SERVE_THREAD = None
MAX_MEMBER = 64 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024


def _inventory(archive):
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) > 512 or len(names) != len(set(names)):
        raise ValueError("Unexpected duplicate or oversized Studio inventory")
    if any(not name.startswith(ROOT) for name in names):
        raise ValueError("Studio ZIP member outside package root")
    if ROOT + "PACKAGE_MANIFEST.json" not in names:
        raise ValueError("Studio ZIP has no package manifest")
    m = json.loads(archive.read(ROOT + "PACKAGE_MANIFEST.json"))
    if m.get("schema") != "merlin-studio-portable/1" or m.get("archive_root") != "Merlin_Studio":
        raise ValueError("Unsupported Studio source manifest")
    records = m.get("files")
    if not isinstance(records, list) or not 1 <= len(records) <= 500:
        raise ValueError("Invalid Studio source inventory")
    expected = {ROOT + "PACKAGE_MANIFEST.json"}
    total = 0
    for record in records:
        path = record.get("path")
        if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
            raise ValueError("Malformed Studio package path")
        parts = PurePosixPath(path)
        if parts.is_absolute() or parts.as_posix() != path or any(x in ("..", ".", "") for x in path.split("/")):
            raise ValueError("Untrusted Studio source path")
        name = ROOT + path
        if name in expected:
            raise ValueError("Repeated Studio source path")
        expected.add(name)
        info = archive.getinfo(name)
        perm = info.external_attr >> 16
        if info.is_dir() or info.flag_bits & 1 or not stat.S_ISREG(perm):
            raise ValueError("Unsafe Studio ZIP member type")
        size = record.get("bytes")
        digest = record.get("sha256")
        if type(size) is not int or size < 0 or size > MAX_MEMBER:
            raise ValueError("Unexpected Studio member size")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Missing Studio member digest")
        data = archive.read(info)
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Studio source digest changed: " + path)
        total += size
        if total > MAX_TOTAL:
            raise ValueError("Studio package exceeds extraction budget")
    if set(names) != expected:
        raise ValueError("Studio ZIP has unknown files")
    return records


def _verify_extracted(target, records):
    for record in records:
        p = target / record["path"]
        if p.is_symlink() or not p.is_file() or p.stat().st_size != record["bytes"]:
            return False
        if hashlib.sha256(p.read_bytes()).hexdigest() != record["sha256"]:
            return False
    return True


def _installed_studio(archive_path, files_path):
    source = Path(archive_path).resolve(strict=True)
    home = Path(files_path).resolve(strict=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = home / ("studio-" + digest[:20])
    with zipfile.ZipFile(source) as archive:
        records = _inventory(archive)
        if target.is_dir():
            if not _verify_extracted(target, records):
                raise ValueError("Installed Merlin source changed; refusing to execute")
            return target
        stage = Path(tempfile.mkdtemp(prefix=".studio-install-", dir=home))
        try:
            for item in records:
                destination = stage.joinpath(*PurePosixPath(item["path"]).parts)
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with archive.open(ROOT + item["path"]) as reader, destination.open("xb") as output:
                    shutil.copyfileobj(reader, output, length=65536)
                destination.chmod(0o600)
            if not _verify_extracted(stage, records):
                raise ValueError("Extracted source failed hash verification")
            os.rename(stage, target)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    return target


def start(archive_path, files_path):
    """Starts once within the application's Python process. Returns the bound port."""
    global RUNNING, SERVE_THREAD
    with LOCK:
        if RUNNING is not None and SERVE_THREAD is not None and SERVE_THREAD.is_alive():
            return int(RUNNING.server_port)
        home = Path(files_path).resolve(strict=True)
        studio = _installed_studio(archive_path, home)
        for path in (str(studio / "core" / "python"), str(studio)):
            if path not in sys.path:
                sys.path.insert(0, path)
        os.environ["MERLIN_ANDROID_APP"] = "1"

        import engine
        import server

        if Path(server.__file__).resolve() != studio / "server.py":
            raise RuntimeError("Different Merlin server was already imported")
        if not getattr(engine, "_ANDROID_POLICY_ACTIVE", False):
            for key in ("network_enabled", "python_enabled", "desktop_enabled", "browser_enabled"):
                engine.DEFAULTS[key] = False
            original = engine.Application.validate_settings

            def protected_settings(values):
                result = original(values)
                for key in ("network_enabled", "python_enabled", "desktop_enabled", "browser_enabled"):
                    if result[key] is True:
                        raise PermissionError(key + " is unavailable in the Android APK")
                return result

            engine.Application.validate_settings = staticmethod(protected_settings)
            engine._ANDROID_POLICY_ACTIVE = True
        state = home / "merlin-user-state"
        state.mkdir(mode=0o700, exist_ok=True)
        state.chmod(0o700)
        RUNNING = server.create_server(host="127.0.0.1", port=8771, data_dir=state, start_bundled=False)
        SERVE_THREAD = threading.Thread(target=RUNNING.serve_forever, name="merlin-studio-http", daemon=True)
        SERVE_THREAD.start()
        return int(RUNNING.server_port)


def stop():
    global RUNNING, SERVE_THREAD
    with LOCK:
        if RUNNING is not None:
            RUNNING.shutdown()
            RUNNING.server_close()
        RUNNING = None
        SERVE_THREAD = None
