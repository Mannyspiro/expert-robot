"""Owner-scoped durable Studio recovery contracts without Docker or external SDK."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portable" / "merlin_studio"))

from storage import Store
from sandbox_recovery import (
    OWNER_KEY, RUN_KEY, RecoveryError, SandboxRecovery,
    list_owned, metadata_for, reconcile_owned, verify_run_cleanup,
)

RUN_A = "a" * 32
RUN_B = "b" * 32
SHA = "1" * 64


def info(sandbox_id, owner_id, run_id, state="RUNNING"):
    return SimpleNamespace(
        id=sandbox_id, metadata={OWNER_KEY: owner_id, RUN_KEY: run_id},
        status=SimpleNamespace(state=state))


class FakeManager:
    def __init__(self, entries=(), *, outage=False, bad_owner=None):
        self.entries = {e.id: e for e in entries}
        self.outage = outage
        self.bad_owner = bad_owner
        self.kill_calls = []
        self.close_count = 0
        self.list_calls = 0

    def list_sandbox_infos(self, criterion):
        self.list_calls += 1
        if self.outage:
            raise OSError("synthetic unreachable control plane")
        matching = [v for v in self.entries.values()
                    if v.metadata.get(OWNER_KEY) == criterion.metadata[OWNER_KEY]]
        matching.sort(key=lambda e: e.id)
        start = (criterion.page - 1) * criterion.page_size
        page = matching[start:start + criterion.page_size]
        if self.bad_owner and page:
            page[0] = info(page[0].id, self.bad_owner, RUN_A)
        return SimpleNamespace(
            sandbox_infos=page,
            pagination=SimpleNamespace(
                has_next_page=start + criterion.page_size < len(matching)))

    def kill_sandbox(self, sandbox_id):
        self.kill_calls.append(sandbox_id)
        if self.outage:
            raise OSError("synthetic kill outage")
        self.entries[sandbox_id].status.state = "TERMINATED"

    def close(self):
        self.close_count += 1


def fake_filter(**fields):
    return SimpleNamespace(**fields)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = Store(Path(self.temporary.name))
        self.owner = self.store.sandbox_owner()
        self.assertEqual(len(self.owner), 32)

    def test_durable_owner_and_intent_survive_new_store(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        second = Store(Path(self.temporary.name))
        self.assertEqual(second.sandbox_owner(), self.owner)
        self.assertEqual(second.sandbox_pending()[0]["run_id"], RUN_A)
        second.sandbox_release(RUN_A)
        self.assertEqual(self.store.sandbox_pending(), [])

    def test_metadata_rejects_incorrect_owner_or_run(self):
        self.assertEqual(metadata_for(self.owner, RUN_A),
                         {OWNER_KEY: self.owner, RUN_KEY: RUN_A})
        for owner, run in [("bad", RUN_A), (self.owner, "bad"), (None, RUN_A)]:
            with self.subTest(owner=owner, run=run), self.assertRaises(RecoveryError):
                metadata_for(owner, run)

    def test_no_pending_skips_unavailable_controller(self):
        created = []
        recovery = SandboxRecovery(self.store, 8080,
                                   factory=lambda port: created.append(port))
        self.assertTrue(recovery.reconcile()["cleanup_confirmed"])
        self.assertTrue(recovery.ready)
        self.assertFalse(recovery.last_report["controller_contacted"])
        self.assertEqual(created, [])
        self.assertEqual(recovery.status()["pending_count"], 0)

    def test_recover_only_our_owned_live_sandboxes(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        other_owner = "f" * 32 if self.owner != "f" * 32 else "e" * 32
        mine = info("owned-one", self.owner, RUN_A)
        foreign = info("not-mine", other_owner, RUN_B)
        manager = FakeManager([mine, foreign])
        recovery = SandboxRecovery(
            self.store, 8080, factory=lambda _: (manager, fake_filter))
        result = recovery.reconcile()
        self.assertEqual(manager.kill_calls, ["owned-one"])
        self.assertEqual(foreign.status.state, "RUNNING")
        self.assertEqual(result["remaining_live"], 0)
        self.assertTrue(recovery.ready)
        self.assertFalse(self.store.sandbox_pending())
        self.assertEqual(manager.close_count, 1)

    def test_wrong_owner_claim_never_killed_and_gate_stays_closed(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        manager = FakeManager([info("claimed", self.owner, RUN_A)],
                              bad_owner="f" * 32 if self.owner != "f" * 32 else "e" * 32)
        recovery = SandboxRecovery(
            self.store, 8080, factory=lambda _: (manager, fake_filter))
        with self.assertRaises(RecoveryError):
            recovery.reconcile()
        self.assertFalse(recovery.ready)
        self.assertEqual(manager.kill_calls, [])
        self.assertEqual(len(self.store.sandbox_pending()), 1)

    def test_controller_outage_blocks_new_work_but_preserves_intent(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        manager = FakeManager(outage=True)
        recovery = SandboxRecovery(
            self.store, 8080, factory=lambda _: (manager, fake_filter))
        with self.assertRaises(RecoveryError):
            recovery.reconcile()
        self.assertFalse(recovery.ready)
        self.assertEqual(recovery.status()["last_error"], "OSError")
        self.assertEqual(len(self.store.sandbox_pending()), 1)
        with self.assertRaises(RecoveryError):
            recovery.reserve(RUN_B, SHA)

    def test_completion_must_not_kill_other_concurrent_run(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        self.store.sandbox_reserve(RUN_B, SHA)
        mine = info("done", self.owner, RUN_A, state="TERMINATED")
        sibling = info("still-running", self.owner, RUN_B)
        manager = FakeManager([mine, sibling])
        recovery = SandboxRecovery(self.store, 8080,
                                   factory=lambda _: (manager, fake_filter))
        recovery.ready = True
        result = recovery.complete(RUN_A)
        self.assertTrue(result["cleanup_confirmed"])
        self.assertEqual(manager.kill_calls, [])
        self.assertEqual(sibling.status.state, "RUNNING")
        self.assertEqual([x["run_id"] for x in self.store.sandbox_pending()], [RUN_B])

    def test_live_own_run_cannot_be_reported_clean(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        manager = FakeManager([info("still-live", self.owner, RUN_A)])
        recovery = SandboxRecovery(self.store, 8080,
                                   factory=lambda _: (manager, fake_filter))
        recovery.ready = True
        clock = iter([0, 20])
        with self.assertRaises(RecoveryError):
            verify_run_cleanup(manager, self.owner, RUN_A,
                               filter_factory=fake_filter,
                               deadline_seconds=1,
                               clock=lambda: next(clock))
        self.assertTrue(self.store.sandbox_pending())

    def test_sandbox_lease_prevents_second_live_server(self):
        self.store.acquire_sandbox_lease()
        another = Store(Path(self.temporary.name))
        try:
            with self.assertRaises(RuntimeError):
                another.acquire_sandbox_lease()
        finally:
            self.store.release_sandbox_lease()
        another.acquire_sandbox_lease()
        another.release_sandbox_lease()

    def test_bounded_pagination_rejects_an_unbounded_owner_set(self):
        owner = self.owner
        many = [info("sandbox-" + str(n), owner, RUN_A) for n in range(29)]
        manager = FakeManager(many)
        with self.assertRaises(RecoveryError):
            list_owned(manager, owner, filter_factory=fake_filter)
        self.assertEqual(manager.kill_calls, [])

    def test_completion_controller_outage_fails_closed(self):
        self.store.sandbox_reserve(RUN_A, SHA)
        manager = FakeManager(outage=True)
        recovery = SandboxRecovery(self.store, 8080,
                                   factory=lambda _: (manager, fake_filter))
        recovery.ready = True
        with self.assertRaises(RecoveryError):
            recovery.complete(RUN_A)
        self.assertFalse(recovery.ready)
        self.assertTrue(self.store.sandbox_pending())


if __name__ == "__main__":
    unittest.main()
