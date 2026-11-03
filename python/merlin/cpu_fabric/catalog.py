"""Verified, bounded model-module catalog and resident-set manager.

Artifacts are opaque bytes. This module never imports or executes artifacts.
Verification and loading use the same byte snapshot to avoid path-swap races.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Callable


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
                   expected_base_sha256: str, available_ram_bytes: int) -> bytes:
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
    base = root.resolve()
    path = (base / manifest.artifact_path).resolve()
    if path != base and base not in path.parents:
        raise CatalogError("artifact path escapes approved root")
    if not path.is_file():
        raise CatalogError("artifact is not a regular file")
    payload = path.read_bytes()
    if sha256(payload).hexdigest() != manifest.artifact_sha256:
        raise CatalogError("artifact SHA-256 mismatch")
    return payload


def verify_manifest(manifest: ModuleManifest, artifact_root: Path,
                    expected_base_sha256: str, available_ram_bytes: int) -> Path:
    """Validate metadata and artifact, returning its resolved path for inspection."""
    _read_verified(manifest, artifact_root, expected_base_sha256, available_ram_bytes)
    return (artifact_root.resolve() / manifest.artifact_path).resolve()


class BoundedModuleManager:
    """LRU resident set; pinned modules cannot be evicted or deactivated.

    loader(payload) returns an opaque runtime handle. unloader(handle) must
    release runtime resources. Neither callback is permitted to execute catalog
    artifact content as Python code.
    """
    def __init__(self, artifact_root: Path, base_model_sha256: str,
                 max_resident_bytes: int, available_ram_bytes: int,
                 loader: Callable[[bytes], object] | None = None,
                 unloader: Callable[[object], None] | None = None):
        if max_resident_bytes <= 0:
            raise ValueError("max_resident_bytes must be positive")
        self.root = Path(artifact_root)
        self.base_hash = base_model_sha256
        self.budget = max_resident_bytes
        self.available_ram = available_ram_bytes
        self.loader = loader or (lambda payload: payload)
        self.unloader = unloader or (lambda handle: None)
        self.catalog: dict[str, ModuleManifest] = {}
        self.resident: OrderedDict[str, tuple[object, int, bool]] = OrderedDict()
        self.resident_bytes = 0
        self._lock = RLock()

    def register(self, manifest: ModuleManifest) -> None:
        with self._lock:
            if manifest.module_id in self.catalog:
                raise CatalogError("duplicate module_id")
            _read_verified(manifest, self.root, self.base_hash, self.available_ram)
            if manifest.estimated_bytes > self.budget:
                raise CatalogError("module exceeds resident memory budget")
            self.catalog[manifest.module_id] = manifest

    def _evict(self, module_id: str) -> None:
        handle, size, pinned = self.resident[module_id]
        if pinned:
            raise CatalogError("pinned module cannot be evicted")
        self.unloader(handle)
        del self.resident[module_id]
        self.resident_bytes -= size

    def activate(self, module_id: str) -> object:
        with self._lock:
            if module_id not in self.catalog:
                raise CatalogError("unknown module")
            manifest = self.catalog[module_id]
            if module_id in self.resident:
                handle, size, pinned = self.resident.pop(module_id)
                self.resident[module_id] = (handle, size, pinned)
                return handle
            payload = _read_verified(manifest, self.root, self.base_hash, self.available_ram)
            while self.resident_bytes + manifest.estimated_bytes > self.budget:
                victim = next((k for k, (_, _, pin) in self.resident.items() if not pin), None)
                if victim is None:
                    raise CatalogError("memory budget blocked by pinned modules")
                self._evict(victim)
            handle = self.loader(payload)
            self.resident[module_id] = (handle, manifest.estimated_bytes, manifest.pinned)
            self.resident_bytes += manifest.estimated_bytes
            return handle

    def deactivate(self, module_id: str) -> None:
        with self._lock:
            if module_id not in self.resident:
                return
            self._evict(module_id)

    def resident_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self.resident.keys())
