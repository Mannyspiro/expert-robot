"""Persistent, owner-scoped OpenSandbox orphan reconciliation for Merlin Studio.

A sandbox is only ever killed if the control-plane metadata includes the exact
persistent owner token of this Studio data directory. If the controller cannot
be contacted or ownership is ambiguous, execution remains disabled rather
than falling back to the host. This does not constitute a kernel isolation
assessment or a guarantee against an unresponsive controller.
"""
from __future__ import annotations

from datetime import timedelta
import os
import re
import threading
import time

OWNER_KEY = "merlin.studio.owner"
RUN_KEY = "merlin.studio.run"
OWNER_PATTERN = re.compile(r"^[a-f0-9]{32}$")
RUN_PATTERN = re.compile(r"^[a-f0-9]{32}$")
TERMINAL = frozenset({"TERMINATED", "DELETED", "FAILED"})
MAX_OWNED = 24
MAX_PAGES = 3
PAGE_SIZE = 10


class RecoveryError(RuntimeError):
    pass


def metadata_for(owner_id, run_id):
    if not (isinstance(owner_id, str) and OWNER_PATTERN.fullmatch(owner_id)):
        raise RecoveryError("invalid persistent Studio sandbox owner")
    if not (isinstance(run_id, str) and RUN_PATTERN.fullmatch(run_id)):
        raise RecoveryError("invalid canonical Studio run identity")
    return {OWNER_KEY: owner_id, RUN_KEY: run_id}


def list_owned(manager, owner_id, *, filter_factory):
    """List bounded pages; verify every returned record's claimed owner."""
    metadata_for(owner_id, "0" * 32)
    owned = {}
    for page in range(1, MAX_PAGES + 1):
        response = manager.list_sandbox_infos(
            filter_factory(metadata={OWNER_KEY: owner_id}, page=page, page_size=PAGE_SIZE))
        items = getattr(response, "sandbox_infos", None)
        page_data = getattr(response, "pagination", None)
        if not isinstance(items, list) or page_data is None or len(items) > PAGE_SIZE:
            raise RecoveryError("OpenSandbox returned an invalid or oversized ownership page")
        for item in items:
            sandbox_id = getattr(item, "id", None)
            meta = getattr(item, "metadata", None)
            if (not isinstance(sandbox_id, str) or len(sandbox_id) > 128
                    or not isinstance(meta, dict)
                    or meta.get(OWNER_KEY) != owner_id):
                raise RecoveryError("OpenSandbox ownership listing is ambiguous")
            if sandbox_id in owned:
                raise RecoveryError("OpenSandbox repeated sandbox identity across pages")
            owned[sandbox_id] = item
            if len(owned) > MAX_OWNED:
                raise RecoveryError("Too many owned sandboxes for bounded automatic recovery")
        more = getattr(page_data, "has_next_page", None)
        if type(more) is not bool:
            raise RecoveryError("OpenSandbox omitted pagination completion evidence")
        if not more:
            return owned
    raise RecoveryError("Owned sandbox list exceeds recovery page budget")


def reconcile_owned(manager, owner_id, *, filter_factory, deadline_seconds=12,
                    clock=time.monotonic, sleep=time.sleep):
    """Terminate only owner-matching records, then verify no live owned items."""
    deadline = clock() + deadline_seconds
    seen = list_owned(manager, owner_id, filter_factory=filter_factory)
    live = {sid: obj for sid, obj in seen.items()
            if getattr(getattr(obj, "status", None), "state", None) not in TERMINAL}
    for sandbox_id in live:
        if clock() >= deadline:
            raise RecoveryError("Owned sandbox cleanup deadline exceeded")
        manager.kill_sandbox(sandbox_id)
    while True:
        remaining = list_owned(manager, owner_id, filter_factory=filter_factory)
        active = [sid for sid, obj in remaining.items()
                  if getattr(getattr(obj, "status", None), "state", None) not in TERMINAL]
        if not active:
            return {"owned_seen": len(seen), "kill_requests": len(live),
                    "remaining_live": 0, "cleanup_confirmed": True}
        if clock() >= deadline:
            raise RecoveryError("Control plane has not confirmed owned sandbox removal")
        sleep(0.2)


def verify_run_cleanup(manager, owner_id, run_id, *, filter_factory,
                       deadline_seconds=10, clock=time.monotonic, sleep=time.sleep):
    """Wait for just this run's sandbox to disappear; never kill other live runs."""
    metadata_for(owner_id, run_id)
    deadline = clock() + deadline_seconds
    while True:
        entries = list_owned(manager, owner_id, filter_factory=filter_factory)
        matches = [x for x in entries.values()
                   if (getattr(x, "metadata", None) or {}).get(RUN_KEY) == run_id]
        active = [x for x in matches
                  if getattr(getattr(x, "status", None), "state", None) not in TERMINAL]
        if not active:
            return {"matching_records": len(matches),
                    "remaining_live": 0, "cleanup_confirmed": True}
        if clock() >= deadline:
            raise RecoveryError("Sandbox deletion for this run was not confirmed")
        sleep(.2)


def make_manager(port):
    # Import optional SDK only when there is an actual pending intent.
    if type(port) is not int or not 1024 <= port <= 65535:
        raise RecoveryError("invalid local OpenSandbox controller port")
    from opensandbox.sync.manager import SandboxManagerSync
    from opensandbox.config import ConnectionConfigSync
    from opensandbox.models.sandboxes import SandboxFilter
    config = ConnectionConfigSync(
        domain="127.0.0.1:" + str(port), protocol="http",
        api_key=os.environ.get("OPEN_SANDBOX_API_KEY") or None,
        request_timeout=timedelta(seconds=4), follow_redirects=False)
    return SandboxManagerSync.create(config), SandboxFilter


class SandboxRecovery:
    """The same object is shared by each ToolSet for this Studio Store."""

    def __init__(self, store, port, *, factory=make_manager):
        self.store = store
        self.owner_id = store.sandbox_owner()
        self.port = port
        self.factory = factory
        self.lock = threading.RLock()
        self.ready = False
        self.last_error = None
        self.last_report = None

    def status(self):
        return {"ready": self.ready, "pending_count": len(self.store.sandbox_pending()),
                "last_error": self.last_error,
                "reconciled": self.last_report is not None}

    def reconcile(self):
        """Block new work until all recorded work from this data directory is verified."""
        with self.lock:
            self.ready = False
            pending = self.store.sandbox_pending()
            if not pending:
                self.last_report = {"owned_seen": 0, "kill_requests": 0,
                                    "remaining_live": 0, "cleanup_confirmed": True,
                                    "controller_contacted": False}
                self.last_error = None
                self.ready = True
                return self.last_report
            manager = None
            try:
                manager, filter_factory = self.factory(self.port)
                report = reconcile_owned(manager, self.owner_id,
                                         filter_factory=filter_factory)
                self.store.sandbox_clear_pending()
                self.last_report = {**report, "controller_contacted": True}
                self.last_error = None
                self.ready = True
                return self.last_report
            except Exception as exc:
                # Preserve the durable pending record and the blocked gate.
                self.last_error = type(exc).__name__
                raise RecoveryError("Owned sandbox cleanup unverified; Python disabled") from exc
            finally:
                if manager is not None:
                    manager.close()

    def reserve(self, run_id, script_hash):
        metadata_for(self.owner_id, run_id)
        if not (isinstance(script_hash, str) and re.fullmatch(r"[a-f0-9]{64}", script_hash)):
            raise RecoveryError("invalid approved script SHA-256")
        with self.lock:
            if not self.ready:
                raise RecoveryError("OpenSandbox recovery gate is blocked")
            # The durable record precedes every potentially successful remote create.
            self.store.sandbox_reserve(run_id, script_hash)
            return self.owner_id

    def complete(self, run_id):
        # Running peers are never killed by a normal completion receipt.
        # The startup reconciliation alone may terminate abandoned work.
        with self.lock:
            manager = None
            try:
                manager, filter_factory = self.factory(self.port)
                receipt = verify_run_cleanup(manager, self.owner_id, run_id,
                                              filter_factory=filter_factory)
                self.store.sandbox_release(run_id)
                self.last_error = None
                return receipt
            except Exception as exc:
                self.ready = False
                self.last_error = type(exc).__name__
                raise RecoveryError("Sandbox cleanup unverified; future Python work blocked") from exc
            finally:
                if manager is not None:
                    manager.close()
