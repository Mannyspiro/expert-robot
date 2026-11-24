"""Adversarial local-process checks; synthetic fixtures, no host qualification."""
from contextlib import contextmanager
import multiprocessing
import os
from queue import Empty
import shutil
import sqlite3
import unittest
from uuid import uuid4

import test_wilborn_security_handover as fixture
from wilborn_ops import security_handover as handover
from wilborn_ops.security_ledger import SecurityLedger,EVENT_CLAIM
from wilborn_ops.security_monitor import SecurityEvent


FORK_AVAILABLE="fork" in multiprocessing.get_all_start_methods()


class HandoverAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.x=fixture.HandoverTests()
        self.addCleanup(self.x.doCleanups)
        self.x.setUp()

    def assert_fenced_before_signing(self,writer):
        invoked=[]
        with self.assertRaises((PermissionError,ValueError,FileNotFoundError,sqlite3.DatabaseError)):
            writer.observe_local(SecurityEvent("tool_denied","demo","synthetic"),
                                 lambda *_:invoked.append(True))
        self.assertEqual(invoked,[],"fenced writer reached its signing callback")

    def process(self,ctx,target):
        p=ctx.Process(target=target)
        def stop():
            if p.is_alive():
                p.terminate()
            p.join(timeout=5)
        self.addCleanup(stop)
        p.start()
        return p

    def join(self,p,expected=0):
        p.join(timeout=10)
        self.assertFalse(p.is_alive(),"child exceeded local process test budget")
        self.assertEqual(p.exitcode,expected)

    def test_enrolled_database_copy_cannot_write_under_another_path(self):
        lease=self.x.activate()
        writer=self.x.control.open_writer(lease)
        destination=self.x.r.a.fixture.root/"copied-ledger"
        destination.mkdir(mode=0o700)
        copied=destination/"successor.sqlite3"
        shutil.copyfile(writer._path,copied)
        copied.chmod(0o600)
        for token in (None,lease):
            with self.subTest(lease=token):
                clone=SecurityLedger(copied,ledger_id=self.x.r.new_id,
                    requester_id="fixture-worker",clock=lambda:self.x.f.now,
                    writer_lease=token,**self.x.r.new_options)
                self.assert_fenced_before_signing(clone)
        self.assertEqual(self.x.observe(writer)["accepted_events"],1)

    def test_missing_or_corrupt_enrollment_metadata_stays_closed(self):
        writer=self.x.control.open_writer(self.x.activate())
        path=writer._path
        original=path.read_bytes()
        mutations=(
            ("missing row","DELETE FROM writer_enrollment",()),
            ("missing table","DROP TABLE writer_enrollment",()),
            ("unsupported version","PRAGMA user_version=2",()),
            ("malformed envelope","UPDATE writer_enrollment SET envelope=?",(b"not-an-envelope",)),
        )
        for label,statement,args in mutations:
            with self.subTest(label=label):
                with sqlite3.connect(path) as db:
                    db.execute(statement,args)
                self.assert_fenced_before_signing(writer)
                path.write_bytes(original)
        self.assertEqual(self.x.observe(writer)["accepted_events"],1)

    def test_missing_or_corrupt_coordinator_stays_closed(self):
        writer=self.x.control.open_writer(self.x.activate())
        path=self.x.directory/"writer-control.sqlite3"
        original=path.read_bytes()
        path.unlink()
        self.assert_fenced_before_signing(writer)
        path.write_bytes(original)
        path.chmod(0o600)
        for statement,args in (
                ("DELETE FROM writer_control",()),
                ("UPDATE writer_control SET envelope=?",(b"not-an-envelope",))):
            with self.subTest(statement=statement):
                with sqlite3.connect(path) as db:
                    db.execute(statement,args)
                self.assert_fenced_before_signing(writer)
                path.write_bytes(original)
        self.assertEqual(self.x.observe(writer)["accepted_events"],1)

    def test_old_grant_after_expiry_and_restart_cannot_upgrade_old_owner(self):
        grant=self.x.grant()
        original=self.x.control.activate(grant)
        writer=self.x.control.open_writer(original)
        self.x.observe(writer)
        self.x.f.now+=86401
        # Fresh synthetic custody is supplied explicitly. The old handover
        # receipt remains historical evidence, not a new activation grant.
        self.x.r.a.custody.retain(self.x.f.anchor())
        self.x.r.anchor()
        restarted=self.x.reopen()
        current=restarted.claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        replayed=restarted.activate(grant)
        self.assertEqual(replayed,original)
        self.assertNotEqual(replayed,current)
        self.assert_fenced_before_signing(writer)
        with self.assertRaises(PermissionError):
            restarted.open_writer(replayed)
        self.assertEqual(self.x.observe(restarted.open_writer(current))["accepted_events"],2)

    def test_active_restart_requires_each_retained_rotation_proof_file(self):
        lease=self.x.activate()
        self.x.observe(self.x.control.open_writer(lease))
        for name in ("continuity.json","review.json"):
            path=self.x.r.directory/name
            original=path.read_bytes()
            for damage in ("changed","missing"):
                with self.subTest(file=name,damage=damage):
                    if damage=="changed":
                        path.write_bytes(b"{}")
                    else:
                        path.unlink()
                    restarted=self.x.reopen()
                    checks=(
                        lambda:restarted.claim_writer(expected_epoch=1,owner_id=str(uuid4())),
                        lambda:restarted.open_writer(lease),
                        restarted.status,
                    )
                    for check in checks:
                        with self.assertRaises((PermissionError,ValueError,FileNotFoundError)):
                            check()
                    path.write_bytes(original)
                    path.chmod(0o600)
                    self.assertEqual(self.x.reopen().status()["epoch"],1)
        current=self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        self.assertEqual(self.x.observe(self.x.control.open_writer(current))["accepted_events"],2)

    def test_expired_current_custody_rejects_restart_until_both_renewed(self):
        lease=self.x.activate()
        self.x.observe(self.x.control.open_writer(lease))
        self.x.f.now+=86401
        with self.assertRaises(PermissionError):
            self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        self.x.r.a.custody.retain(self.x.f.anchor())
        with self.assertRaises(PermissionError):
            self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        self.x.r.anchor()
        current=self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        self.assertEqual(current.epoch,2)
        self.assertEqual(self.x.observe(self.x.control.open_writer(current))["accepted_events"],2)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_two_process_restart_claims_have_exactly_one_winner(self):
        self.x.activate()
        ctx=multiprocessing.get_context("fork")
        start=ctx.Event()
        outcomes=ctx.Queue()
        self.addCleanup(outcomes.close)
        def claim():
            start.wait(timeout=5)
            try:
                result=self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
                outcomes.put(("won",result))
            except PermissionError:
                outcomes.put(("fenced",None))
        children=[self.process(ctx,claim),self.process(ctx,claim)]
        start.set()
        results=[outcomes.get(timeout=10),outcomes.get(timeout=10)]
        for child in children:
            self.join(child)
        self.assertEqual(sorted(x[0] for x in results),["fenced","won"])
        winner=next(x[1] for x in results if x[0]=="won")
        self.assertEqual(self.x.reopen().status()["epoch"],2)
        self.assertEqual(self.x.observe(self.x.control.open_writer(winner))["accepted_events"],1)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_restart_claim_waits_until_inflight_event_commits(self):
        lease=self.x.activate()
        ctx=multiprocessing.get_context("fork")
        entered=ctx.Event()
        release=ctx.Event()
        claim_start=ctx.Event()
        claim_entered=ctx.Event()
        events=ctx.Queue()
        claims=ctx.Queue()
        self.addCleanup(events.close)
        self.addCleanup(claims.close)
        self.addCleanup(release.set)
        def write():
            writer=self.x.reopen().open_writer(lease)
            def sign(binding,now):
                entered.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("signer release budget")
                return self.x.f.sign(self.x.r.sensor,EVENT_CLAIM,binding,now,"artifact-integrity")
            events.put(writer.observe_local(SecurityEvent("tool_denied","demo","synthetic"),sign))
        def claim():
            claim_start.wait(timeout=5)
            claim_entered.set()
            current=self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
            claims.put(current)
        # Both forks happen before a connection acquires a SQLite lock.
        claimer=self.process(ctx,claim)
        writer=self.process(ctx,write)
        self.assertTrue(entered.wait(timeout=5))
        claim_start.set()
        self.assertTrue(claim_entered.wait(timeout=5))
        with self.assertRaises(Empty):
            claims.get(timeout=0.2)
        release.set()
        accepted=events.get(timeout=10)
        current=claims.get(timeout=10)
        self.join(writer)
        self.join(claimer)
        self.assertEqual(accepted["revision"],2)
        self.assertEqual(current.epoch,2)
        active=self.x.reopen().open_writer(current)
        self.assertEqual(active.report()["accepted_events"],1)
        self.assertEqual(self.x.observe(active)["revision"],3)
        with self.assertRaises(PermissionError):
            self.x.control.open_writer(lease)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_abrupt_exit_after_each_fence_can_resume_preparation(self):
        ctx=multiprocessing.get_context("fork")
        for boundary in ("successor","predecessor"):
            def crash():
                control=self.x.reopen()
                original=control._freeze
                def freeze(role):
                    original(role)
                    if role==boundary:
                        os._exit(71)
                control._freeze=freeze
                control.prepare()
                os._exit(1)
            with self.subTest(boundary=boundary):
                child=self.process(ctx,crash)
                self.join(child,71)
                self.assertEqual(self.x.reopen().status()["phase"],"preparing")
                self.assert_fenced_before_signing(self.x.r.ledger())
        self.assert_fenced_before_signing(self.x.f.ledger)
        current=self.x.activate()
        self.assertEqual(self.x.observe(self.x.reopen().open_writer(current))["revision"],2)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_abrupt_exit_before_ledger_commit_rolls_back_event(self):
        lease=self.x.activate()
        before=self.x.control.open_writer(lease).report()
        ctx=multiprocessing.get_context("fork")
        def crash():
            writer=self.x.reopen().open_writer(lease)
            original=writer._save
            def save(db,state,**kwargs):
                original(db,state,**kwargs)
                os._exit(72)
            writer._save=save
            self.x.observe(writer)
            os._exit(1)
        child=self.process(ctx,crash)
        self.join(child,72)
        writer=self.x.reopen().open_writer(lease)
        self.assertEqual(writer.report(),before)
        self.assertEqual(self.x.observe(writer)["accepted_events"],1)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_abrupt_exit_after_ledger_commit_preserves_event_on_takeover(self):
        lease=self.x.activate()
        ctx=multiprocessing.get_context("fork")
        def crash():
            writer=self.x.reopen().open_writer(lease)
            original=handover._control_transaction
            @contextmanager
            def after_ledger_commit(path):
                with original(path) as db:
                    yield db
                    os._exit(73)
            handover._control_transaction=after_ledger_commit
            self.x.observe(writer)
            os._exit(1)
        child=self.process(ctx,crash)
        self.join(child,73)
        restarted=self.x.reopen()
        current=restarted.claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        writer=restarted.open_writer(current)
        self.assertEqual(writer.report()["accepted_events"],1)
        self.assertEqual(self.x.observe(writer)["accepted_events"],2)


if __name__=="__main__":
    unittest.main()
