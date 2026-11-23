"""Disabled-by-default Obsidian review surface for the local Merlin Studio UI.

This object never appears in the agent tool registry or model prompt. The
server authenticates mutating HTTP calls before invoking this controller.
Real human presence cannot be proven by a browser token alone: model/tool
authorization and a separate host security review remain mandatory.
"""
from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
import secrets
import threading
import time

from merlin.knowledge_graph import MerlinKnowledgeGraph
from merlin.obsidian_promotion import ObsidianNotePromotion
from merlin.obsidian_vault_bridge import ObsidianVaultBridge, _safe_relative

REVIEW_MAX_BYTES = 16 * 1024
PENDING_LIFETIME_SECONDS = 120
MAX_VISIBLE_NOTES = 200
MAX_SEARCH_RESULTS = 30


class SecondBrainPanel:
    def __init__(self, vault_root, store, *, enable_import=False):
        if type(enable_import) is not bool:
            raise ValueError("import mode must be an explicit Boolean")
        root = Path(vault_root).resolve(strict=True)
        data = store.root.resolve(strict=True)
        if root == data or root in data.parents or data in root.parents:
            raise ValueError("Obsidian vault and Merlin data store must be separate")
        self.vault = ObsidianVaultBridge(root)
        self.import_enabled = enable_import
        self._lock = threading.RLock()
        self._pending = None
        self.promotion = None
        if enable_import:
            # This is Merlin's canonical graph type, stored under the
            # existing operator-selected Studio data directory.
            graph = MerlinKnowledgeGraph(store.root / "knowledge_graph.sqlite3")
            self.promotion = ObsidianNotePromotion(self.vault, store.registry, graph)
            self.project_id = store.PROJECT

    def status(self):
        return {
            "schema": "merlin-studio-second-brain-status/1",
            "configured": True,
            "import_enabled": self.import_enabled,
            "read_only_default": True,
            "requires_local_session": True,
            "encrypted_storage_qualified": False,
            "source_claims_verified": False,
            "max_review_bytes": REVIEW_MAX_BYTES,
            "production_qualified": False,
        }

    def inventory(self):
        data = self.vault.read()
        return {
            "schema": "merlin-studio-second-brain-inventory/1",
            "status": data["status"],
            "notes_scanned": data["notes_scanned"],
            "notes": [
                {"path": n["path"], "title": n["title"], "sha256": n["sha256"],
                 "backlink_count": len(n["backlinks"])}
                for n in data["notes"][:MAX_VISIBLE_NOTES]
            ],
            "truncated": len(data["notes"]) > MAX_VISIBLE_NOTES,
            "omissions_count": len(data["omissions"]),
            "source_content_emitted": False,
        }

    def search(self, value):
        if set(value) != {"query"} or not isinstance(value["query"], str):
            raise ValueError("only a bounded local search query is accepted")
        results = self.vault.search(value["query"], limit=MAX_SEARCH_RESULTS,
                                    include_snippets=False)
        return {
            "schema": "merlin-studio-second-brain-search/1",
            "status": results["status"],
            "results": results["results"],
            "omissions_count": len(results["omissions"]),
            "source_content_emitted": False,
        }

    def review(self, value):
        if set(value) != {"path"} or not isinstance(value["path"], str):
            raise ValueError("review requires one relative note path")
        path = _safe_relative(value["path"])
        data = self.vault.read()
        note = next((n for n in data["notes"] if n["path"] == path), None)
        if note is None:
            raise ValueError("note not present in the bounded vault inventory")
        raw = self.vault._read(path, budget_bytes=REVIEW_MAX_BYTES)
        if len(raw) > REVIEW_MAX_BYTES or hashlib.sha256(raw).hexdigest() != note["sha256"]:
            raise RuntimeError("note changed or exceeds the exact review limit")
        if not raw:
            raise ValueError("empty notes cannot be reviewed")
        decoded = raw.decode("utf-8")
        with self._lock:
            self._pending = None
            permission = None
            if self.import_enabled:
                if data["status"] != "indexed":
                    raise PermissionError("incomplete vault inventory; durable import blocked")
                preview = self.promotion.preview(self.project_id, path, vault_label="studio")
                if (preview["source_sha256"] != note["sha256"]
                        or preview["size_bytes"] != len(raw)
                        or preview["inventory_status"] != "indexed"):
                    raise RuntimeError("review preview changed during source inspection")
                nonce = secrets.token_urlsafe(32)
                self._pending = (nonce, preview, time.monotonic() + PENDING_LIFETIME_SECONDS)
                permission = {"nonce": nonce, "preview_id": preview["preview_id"],
                              "expires_in_seconds": PENDING_LIFETIME_SECONDS}
            return {
                "schema": "merlin-studio-second-brain-review/1",
                "path": path, "sha256": note["sha256"], "size_bytes": len(raw),
                "content": decoded, "complete_content": True,
                "inventory_status": data["status"], "import": permission,
                "warning": "An approved import persists plaintext in Merlin's local registry. Do not import sensitive information until storage and retention controls are reviewed.",
                "source_claims_verified": False, "production_qualified": False,
            }

    def discard(self, value):
        if set(value) != {"nonce"} or not isinstance(value["nonce"], str):
            raise ValueError("one valid review nonce required")
        with self._lock:
            pending = self._pending
            if pending is None or not hmac.compare_digest(pending[0], value["nonce"]):
                raise PermissionError("review is missing or no longer current")
            self._pending = None
        return {"discarded": True, "durable_artifact_removed": False}

    def import_reviewed(self, value):
        """Consume one exact review authorization; never auto-retry a failed write."""
        if not self.import_enabled or self.promotion is None:
            raise PermissionError("second-brain durable import was not enabled at startup")
        if set(value) != {"nonce", "preview_id", "confirm"}:
            raise ValueError("exact import confirmation fields required")
        nonce, preview_id, confirmed = value["nonce"], value["preview_id"], value["confirm"]
        if not isinstance(nonce, str) or not isinstance(preview_id, str) or confirmed is not True:
            raise PermissionError("explicit exact review confirmation required")
        with self._lock:
            pending = self._pending
            if pending is None:
                raise PermissionError("no pending local review")
            recorded_nonce, preview, expires = pending
            if not hmac.compare_digest(recorded_nonce, nonce):
                raise PermissionError("incorrect local review nonce")
            # Consume before any canonical mutation. Failed/interrupted writes
            # require a new explicit review; no background replay.
            self._pending = None
            if time.monotonic() >= expires or not hmac.compare_digest(preview["preview_id"], preview_id):
                raise PermissionError("review expired or source identity changed")
            receipt = self.promotion.promote(
                preview,
                operator_approve=lambda item: (
                    item.get("preview_id") == preview_id
                    and item.get("source_sha256") == preview["source_sha256"]
                ),
            )
            inspection = self.promotion.inspect(preview)
            if inspection["status"] != "complete_unverified":
                raise RuntimeError("import interrupted: operator reconciliation required")
            return {"receipt": receipt, "inspection": inspection,
                    "source_claims_verified": False, "production_qualified": False}

    def close(self):
        with self._lock:
            self._pending = None
