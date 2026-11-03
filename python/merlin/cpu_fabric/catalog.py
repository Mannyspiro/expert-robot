"""Verified, bounded model-module catalog and resident-set manager.

Artifacts are treated as opaque bytes: this module never imports or executes them.
Only catalog entries under an explicit artifact root can be loaded.
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


def _safe_artifact(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    base = root.resolve()
    if candidate != base and base not in candidate.parents:
        raise CatalogError("artifact path escapes approved root")
    if not candidate.is_file():
        raise CatalogError("artifact is not a regular file")
    return candidate


def verify_manifest(manifest: ModuleManifest, artifact_root: Path,
                    expected_base_sha256: str, available_ram_bytes: int) -> Path:
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
    path = _safe_artifact(artifact_root, manifest.artifact_path)
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != manifest.artifact_sha256:
        raise CatalogError("artifact SHA-256 mismatch")
    return path


class BoundedModuleManager:
    """LRU resident set; pinned modules cannot be evicted.

    loader(path) returns an opaque in-memory handle. No dynamic imports occur.
    """
    def __init__(self, artifact_root: Path, base_model_sha256: str,
                 max_resident_bytes: int, available_ram_bytes: int,
                 loader: Callable[[Path], object] | None = None):
        if max_resident_bytes <= 0:
            raise ValueError("max_resident_bytes must be positive")
        self.root = Path(artifact_root)
        self.base_hash = base_model_sha256
        self.budget = max_resident_bytes
        self.available_ram = available_ram_bytes
        self.loader = loader or (lambda p: p.read_bytes())
        self.catalog: dict[str, ModuleManifest] = {}
        self.resident: OrderedDict[str, tuple[object, int, bool]] = OrderedDict()
        self.resident_bytes = 0
        self._lock = RLock()

    def register(self, manifest: ModuleManifest) -> None:
        with self._lock:
            if manifest.module_id in self.catalog:
                raise CatalogError("duplicate module_id")
            verify_manifest(manifest, self.root, self.base_hash, self.available_ram)
            if manifest.estimated_bytes > self.budget:
                raise CatalogError("module exceeds resident memory budget")
            self.catalog[manifest.module_id] = manifest

    def activate(self, module_id: str) -> object:
        with self._lock:
            if module_id not in self.catalog:
                raise CatalogError("unknown module")
            manifest = self.catalog[module_id]
            if module_id in self.resident:
                handle, size, pinned = self.resident.pop(module_id)
                self.resident[module_id] = (handle, size, pinned)
                return handle
            path = verify_manifest(manifest, self.root, self.base_hash, self.available_ram)
            while self.resident_bytes + manifest.estimated_bytes > self.budget:
                victim = next((k for k, (_, _, pin) in self.resident.items() if not pin), None)
                if victim is None:
                    raise CatalogError("memory budget blocked by pinned modules")
                _, size, _ = self.resident.pop(victim)
                self.resident_bytes -= size
            handle = self.loader(path)
            self.resident[module_id] = (handle, manifest.estimated_bytes, manifest.pinned)
            self.resident_bytes += manifest.estimated_bytes
            return handle

    def deactivate(self, module_id: str) -> None:
        with self._lock:
            item = self.resident.get(module_id)
            if item is None:
                return
            if item[2]:
                raise CatalogError("pinned module cannot be deactivated")
            _, size, _ = self.resident.pop(module_id)
            self.resident_bytes -= size

    def resident_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self.resident.keys())
