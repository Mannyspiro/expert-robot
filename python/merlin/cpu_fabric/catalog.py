"""Verified, bounded model-module catalog and resident-set manager.

Artifacts are opaque bytes. This module never imports or executes artifacts.
Verification and loading use one open descriptor and a bounded in-memory
snapshot; transient artifact bytes have a separate cap from resident bytes.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import Callable
import os
import uuid


@dataclass(frozen=True)
class ModuleManifest:
    module_id: str
    artifact_path: str
    artifact_sha256: str
    base_model_sha256: str
    module_type: str
    task_scope: tuple[str, ...]
    precision: str
    estimated_bytes: int
    min_ram_bytes: int
    quality_eval_id: str
    verifier_id: str
    rollback_ref: str
    approved: bool = False
    pinned: bool = False


class CatalogError(ValueError):
    pass


def _read_verified(manifest: ModuleManifest, root: Path,
                   expected_base_sha256: str, available_ram_bytes: int,
                   max_artifact_bytes: int) -> bytearray:
    if not manifest.approved:
        raise CatalogError("module is not approved")
    if manifest.base_model_sha256 != expected_base_sha256:
        raise CatalogError("base-model compatibility hash mismatch")
    if len(manifest.artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in manifest.artifact_sha256):
        raise CatalogError("artifact_sha256 must be lowercase SHA-256 hex")
    if manifest.estimated_bytes <= 0 or manifest.min_ram_bytes < 0:
        raise CatalogError("invalid memory estimate")
    if manifest.min_ram_bytes > available_ram_bytes:
        raise CatalogError("insufficient available RAM")
    if not manifest.module_id or not manifest.task_scope or not manifest.verifier_id or not manifest.quality_eval_id or not manifest.rollback_ref:
        raise CatalogError("manifest is missing required qualification metadata")
    if max_artifact_bytes <= 0:
        raise CatalogError("max_artifact_bytes must be positive")
    base = root.resolve()
    path = (base / manifest.artifact_path).resolve()
    if path != base and base not in path.parents:
        raise CatalogError("artifact path escapes approved root")
    if not path.is_file():
        raise CatalogError("artifact is not a regular file")
    try:
        with path.open("rb") as stream:
            size = os.fstat(stream.fileno()).st_size
            if size > max_artifact_bytes:
                raise CatalogError("artifact exceeds transient memory limit")
            digest = sha256()
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
            if digest.hexdigest() != manifest.artifact_sha256:
                raise CatalogError("artifact SHA-256 mismatch")
            stream.seek(0)
            payload = bytearray()
            while True:
                chunk = stream.read(min(1024 * 1024, max_artifact_bytes + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) > max_artifact_bytes:
                    raise CatalogError("artifact exceeds transient memory limit")
            if len(payload) != size:
                raise CatalogError("artifact changed while verified snapshot was read")
            return payload
    except OSError as exc:
        raise CatalogError("artifact could not be read") from exc


def verify_manifest(manifest: ModuleManifest, artifact_root: Path,
                    expected_base_sha256: str, available_ram_bytes: int,
                    max_artifact_bytes: int = 64 * 1024 * 1024) -> Path:
    """Validate metadata and artifact, returning its resolved path for inspection."""
    _read_verified(manifest, artifact_root, expected_base_sha256,
                   available_ram_bytes, max_artifact_bytes)
    return (artifact_root.resolve() / manifest.artifact_path).resolve()


class BoundedModuleManager:
    """LRU resident set with a separate cap on transient artifact snapshots.

    loader(payload) returns an opaque runtime handle. unloader(handle) must
    release runtime resources. Neither callback may execute artifact content
    as Python code. The loader receives a bytearray to avoid a second full-size
    immutable bytes copy at this boundary.
    """
    def __init__(self, artifact_root: Path, base_model_sha256: str,
                 max_resident_bytes: int, available_ram_bytes: int,
                 loader: Callable[[bytearray], object] | None = None,
                 unloader: Callable[[object], None] | None = None,
                 event_sink: Callable[[dict], None] | None = None,
                 run_id: str | None = None,
                 max_artifact_bytes: int | None = None):
        if max_resident_bytes <= 0:
            raise ValueError("max_resident_bytes must be positive")
        self.root = Path(artifact_root)
        self.base_hash = base_model_sha256
        self.budget = max_resident_bytes
        self.available_ram = available_ram_bytes
        self.max_artifact_bytes = max_artifact_bytes if max_artifact_bytes is not None else max_resident_bytes
        if self.max_artifact_bytes <= 0:
            raise ValueError("max_artifact_bytes must be positive")
        self.loader = loader or (lambda payload: payload)
        self.unloader = unloader or (lambda handle: None)
        self.event_sink = event_sink
        self.run_id = run_id or str(uuid.uuid4())
        self.catalog: dict[str, ModuleManifest] = {}
        self.resident: OrderedDict[str, tuple[object, int, bool]] = OrderedDict()
        self.resident_bytes = 0
        self._lock = RLock()

    def register(self, manifest: ModuleManifest) -> None:
        with self._lock:
            if manifest.module_id in self.catalog:
                raise CatalogError("duplicate module_id")
            _read_verified(manifest, self.root, self.base_hash,
                           self.available_ram, self.max_artifact_bytes)
            if manifest.estimated_bytes > self.budget:
                raise CatalogError("module exceeds resident memory budget")
            self.catalog[manifest.module_id] = manifest

    @staticmethod
    def _rss_bytes() -> int | None:
        """Best-effort current RSS on Linux; None where unavailable."""
        try:
            with open("/proc/self/statm", "r", encoding="ascii") as stream:
                resident_pages = int(stream.read().split()[1])
            return resident_pages * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError, AttributeError):
            return None

    def _emit(self, module_id: str, operation: str, started: float,
              rss_before: int | None, *, outcome: str, artifact_bytes: int = 0,
              error_type: str | None = None) -> None:
        if self.event_sink is None:
            return
        rss_after = self._rss_bytes()
        event = {
            "schema": "merlin-loader-event/1", "source": "runtime",
            "kind": "resource.sample", "run_id": self.run_id,
            "task_id": module_id,
            "duration_ms": max(0.0, (perf_counter() - started) * 1000),
            "memory_bytes": rss_after,
            "payload": {
                "component": "module_loader", "operation": operation,
                "artifact_bytes": artifact_bytes,
                "resident_module_bytes": self.resident_bytes,
                "transient_artifact_limit_bytes": self.max_artifact_bytes,
                "rss_before_bytes": rss_before, "rss_after_bytes": rss_after,
                "rss_delta_bytes": (rss_after - rss_before)
                    if rss_before is not None and rss_after is not None else None,
                "rss_measurement": "linux_proc_statm_current_rss" if rss_after is not None else "unavailable",
                "outcome": outcome, "error_type": error_type,
            },
        }
        try:
            self.event_sink(event)
        except Exception:
            pass

    def _evict(self, module_id: str) -> None:
        handle, size, pinned = self.resident[module_id]
        if pinned:
            raise CatalogError("pinned module cannot be evicted")
        started, rss_before = perf_counter(), self._rss_bytes()
        try:
            self.unloader(handle)
        except Exception as exc:
            self._emit(module_id, "unload", started, rss_before,
                       outcome="failed", error_type=type(exc).__name__)
            raise
        del self.resident[module_id]
        self.resident_bytes -= size
        self._emit(module_id, "unload", started, rss_before, outcome="succeeded")

    def activate(self, module_id: str) -> object:
        with self._lock:
            if module_id not in self.catalog:
                raise CatalogError("unknown module")
            manifest = self.catalog[module_id]
            if module_id in self.resident:
                handle, size, pinned = self.resident.pop(module_id)
                self.resident[module_id] = (handle, size, pinned)
                return handle
            while self.resident_bytes + manifest.estimated_bytes > self.budget:
                victim = next((k for k, (_, _, pin) in self.resident.items() if not pin), None)
                if victim is None:
                    raise CatalogError("memory budget blocked by pinned modules")
                self._evict(victim)
            started, rss_before = perf_counter(), self._rss_bytes()
            payload = None
            try:
                payload = _read_verified(manifest, self.root, self.base_hash,
                                         self.available_ram, self.max_artifact_bytes)
                handle = self.loader(payload)
            except Exception as exc:
                self._emit(module_id, "load", started, rss_before,
                           outcome="failed",
                           artifact_bytes=len(payload) if payload is not None else 0,
                           error_type=type(exc).__name__)
                raise
            self.resident[module_id] = (handle, manifest.estimated_bytes, manifest.pinned)
            self.resident_bytes += manifest.estimated_bytes
            self._emit(module_id, "load", started, rss_before,
                       outcome="succeeded", artifact_bytes=len(payload))
            return handle

    def deactivate(self, module_id: str) -> None:
        with self._lock:
            if module_id not in self.resident:
                return
            self._evict(module_id)

    def resident_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self.resident.keys())
