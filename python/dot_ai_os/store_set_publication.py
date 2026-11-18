"""Select a prepared LMS store generation in a private, host-owned Linux catalog.

The host supplies trusted pins and immutable, already-closed generation files.
All selectors must use this API. Capture, catalog creation, retention and
cross-store writer coordination are separate operations.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .recovery import (RecoveryError, SnapshotBounds, _Budget, _digest, _directory,
                       _path, _read_file, verify_snapshot)

DATABASES = ("learning.sqlite3", "hypotheses.sqlite3", "graph.sqlite3")


class SelectionUncertain(RecoveryError):
    """CURRENT was replaced, but its parent sync did not complete."""


def _pointer(value):
    if (not isinstance(value, dict) or set(value) != {"generation", "manifest_sha256"}
            or not isinstance(value["generation"], str)
            or not re.fullmatch(r"generation-[a-zA-Z0-9_-]{1,80}", value["generation"])):
        raise RecoveryError("invalid generation selector")
    _digest(value["manifest_sha256"])
    return value


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_json(path, limit):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise RecoveryError("publication metadata too large")
    return raw, json.loads(raw)


def select_generation(catalog, candidate, previous):
    """Compare and replace CURRENT. Retry with the original candidate and previous.

    A selected candidate is verified and synced again before acknowledgement.
    A different current generation prevents an old retry from rolling it back.
    """
    catalog = _path(catalog)
    _directory(catalog)
    candidate = _pointer(candidate)
    if previous is not None:
        _pointer(previous)
    current = _path(catalog / "CURRENT")
    lock_fd = os.open(catalog, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            _, value = _read_json(current, 1024)
            selected = _pointer(value)
        except FileNotFoundError:
            selected = None
        if selected != candidate and selected != previous:
            raise RecoveryError("current generation changed")
        bundle = _path(catalog / candidate["generation"])
        _directory(bundle)
        if {path.name for path in bundle.iterdir()} != {*DATABASES, "registry", "pins.json"}:
            raise RecoveryError("unexpected store-set contents")
        raw, pins = _read_json(_path(bundle / "pins.json"), 4096)
        if (hashlib.sha256(raw).hexdigest() != candidate["manifest_sha256"]
                or not isinstance(pins, dict) or set(pins) != {*DATABASES, "registry"}):
            raise RecoveryError("store-set manifest mismatch")
        bounds = SnapshotBounds()
        budget = _Budget(bounds)
        for name in DATABASES:
            path = _path(bundle / name)
            _read_file(path, bounds.max_db_bytes, budget, expected=_digest(pins[name]))
            _sync(path)
        registry = bundle / "registry"
        verify_snapshot(registry, pins["registry"], bounds)
        # The canonical verifier checks the complete snapshot tree and its bounds.
        for directory, _, files in os.walk(registry, topdown=False, onerror=_raise_walk_error):
            for name in files:
                _sync(Path(directory) / name)
            _sync(directory)
        _sync(bundle / "pins.json")
        _sync(bundle)
        _sync(catalog)
        if selected != candidate:
            pending = None
            try:
                with tempfile.NamedTemporaryFile(dir=catalog, prefix=".pointer-", delete=False) as stream:
                    pending = Path(stream.name)
                    stream.write(json.dumps(candidate, sort_keys=True).encode())
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(pending, current)
            finally:
                if pending is not None:
                    pending.unlink(missing_ok=True)
        try:
            if selected == candidate:
                _sync(current)
            _sync(catalog)
        except OSError as exc:
            raise SelectionUncertain("reconcile CURRENT against the original candidate before retry") from exc
        return candidate
    finally:
        os.close(lock_fd)


def _raise_walk_error(error):
    raise error
