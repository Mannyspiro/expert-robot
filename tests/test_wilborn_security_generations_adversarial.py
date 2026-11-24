"""Synthetic continuation failures using real ledger/receipt/process boundaries."""
from contextlib import contextmanager
import multiprocessing
import os
from pathlib import Path
from queue import Empty
import shutil
import sqlite3
import unittest
from uuid import uuid4

import test_wilborn_security_handover as fixtures
from test_wilborn_attested_integration import Signer
from wilborn_ops import security_handover as handover
from wilborn_ops.security_archive import ARCHIVE_CLAIM,stage_archive,seal_archive
from wilborn_ops.security_handover import WriterHandover,CLAIM
from wilborn_ops.security_ledger import (
    SecurityLedger,MAX_HISTORY,ANCHOR_CLAIM,EVENT_CLAIM,REVIEW_CLAIM,
    anchor_bindings,event_bindings,review_bindings)
from wilborn_ops.security_monitor import SecurityEvent
from wilborn_ops.security_recovery import AnchorCustody
from wilborn_ops.security_rotation import CLAIM as ROTATION_CLAIM,stage_rotation,seal_rotation


FORK_AVAILABLE="fork" in multiprocessing.get_all_start_methods()


class GenerationAdversarialTests(unittest.TestCase):
    def setUp(self):
        self.x=fixtures.HandoverTests()
        self.addCleanup(self.x.doCleanups)
        self.x.setUp()
        self.grant_ab=self.x.grant()
        self.lease_ab=self.x.control.activate(self.grant_ab)
        self.writer_b=self.x.control.open_writer(self.lease_ab)
        self.root=self.x.r.a.fixture.root

    def child(self,label,*,parent=None,successor_id=None,successor_options=None,control_directory=None):
        """Build a separately reviewed candidate from an active segment."""
        f=self.x.f
        if parent is None:
            parent={"control":self.x.control,"writer":self.writer_b,
                    "custody":self.x.r.successor,"options":self.x.r.new_options,
                    "anchorer":self.x.r.anchorer}
        old_writer=parent["writer"]
        old_custody=parent["custody"]
        old_report=old_writer.report()
        old_binding=anchor_bindings(old_custody._id,old_report["revision"],old_report["state_sha256"])
        old_custody.retain({"bindings":old_binding,"attestation":f.sign(parent["anchorer"],
            ANCHOR_CLAIM,old_binding,f.now,"independent-reproduction")})
        archive_reviewer=Signer(label+"-archive")
        archive=self.root/(label+"-archive")
        old_options=parent["options"]
        source=old_writer._path
        staged=stage_archive(source,archive,custody=old_custody,options=old_options)
        seal_archive(archive,custody=old_custody,options=old_options,
            reviewer_keys=archive_reviewer.trust,review_attestation=f.sign(archive_reviewer,
            ARCHIVE_CLAIM,staged["review_bindings"],f.now,"independent-reproduction"))
        sensor=Signer(label+"-sensor")
        operator=Signer(label+"-operator")
        anchorer=Signer(label+"-anchor")
        rotation_reviewer=Signer(label+"-rotation")
        handover_reviewer=Signer(label+"-handover")
        ledger_id=successor_id or str(uuid4())
        custody_dir=self.root/(label+"-custody")
        custody_dir.mkdir(mode=0o700)
        custody=AnchorCustody(custody_dir,ledger_id=ledger_id,trust=anchorer.trust,
            requester_id="fixture-worker",clock=lambda:f.now,create=True)
        new_options=dict(master_key=os.urandom(32),key_id=label+"-key",
                         sensor_keys=sensor.trust,operator_keys=operator.trust)
        if successor_options:
            new_options.update(successor_options)
        stage=self.root/(label+"-stage")
        rotation=dict(predecessor=old_custody,successor=custody,old_options=old_options,
            new_options=new_options,archive_review_keys=archive_reviewer.trust,
            reserve_revisions=MAX_HISTORY-old_report["revision"])
        rotated=stage_rotation(source,archive,stage,**rotation)
        ledger=SecurityLedger(stage/"successor.sqlite3",ledger_id=ledger_id,
            requester_id="fixture-worker",clock=lambda:f.now,**new_options)
        report=ledger.report()
        binding=anchor_bindings(ledger_id,report["revision"],report["state_sha256"])
        custody.retain({"bindings":binding,"attestation":f.sign(anchorer,ANCHOR_CLAIM,
                        binding,f.now,"independent-reproduction")})
        seal_rotation(source,archive,stage,**rotation,rotation_review_keys=rotation_reviewer.trust,
            review_attestation=f.sign(rotation_reviewer,ROTATION_CLAIM,
                rotated["review_bindings"],f.now,"independent-reproduction"))
        directory=control_directory if control_directory is not None else self.root/(label+"-control")
        if control_directory is None:
            directory.mkdir(mode=0o700)
        kwargs=dict(handover_id=str(uuid4()),source=source,archive=archive,stage=stage,
            **rotation,rotation_review_keys=rotation_reviewer.trust,
            handover_review_keys=handover_reviewer.trust,previous=parent["control"])
        control=WriterHandover(directory,**kwargs,create=True,owner_id=str(uuid4()))
        return {"control":control,"directory":directory,"kwargs":kwargs,
                "reviewer":handover_reviewer,"sensor":sensor,"ledger":ledger,
                "archive":archive,"custody":custody,"anchorer":anchorer,
                "options":new_options}

    def reopen(self,child):
        return WriterHandover(child["directory"],**child["kwargs"])

    def activate(self,child):
        binding=child["control"].prepare()
        grant=self.x.f.sign(child["reviewer"],CLAIM,binding,self.x.f.now,"independent-reproduction")
        lease=child["control"].activate(grant)
        child["writer"]=child["control"].open_writer(lease)
        return lease

    def observe_child(self,child,writer):
        return writer.observe_local(SecurityEvent("integrity_failure","demo","synthetic"),
            lambda b,now:self.x.f.sign(child["sensor"],EVENT_CLAIM,b,now,"artifact-integrity"))

    def assert_fenced(self,writer):
        invoked=[]
        with self.assertRaises((PermissionError,ValueError,FileNotFoundError,sqlite3.DatabaseError)):
            writer.observe_local(SecurityEvent("tool_denied","demo","synthetic"),
                                 lambda *_:invoked.append(True))
        self.assertEqual(invoked,[])

    def process(self,ctx,target):
        child=ctx.Process(target=target)
        def stop():
            if child.is_alive():
                child.terminate()
            child.join(timeout=5)
        self.addCleanup(stop)
        child.start()
        return child

    def join(self,child,expected=0):
        child.join(timeout=10)
        self.assertFalse(child.is_alive(),"generation process exceeded test budget")
        self.assertEqual(child.exitcode,expected)

    def test_retired_genesis_parent_cannot_reenter_any_writer_lifecycle(self):
        # Genesis is intentional: an accidental retired->ready downgrade
        # must not be masked by the old inspector rejecting successor events.
        child=self.child("genesis")
        with sqlite3.connect(self.writer_b._path) as db:
            enrollment=db.execute("SELECT envelope FROM writer_enrollment").fetchone()[0]
        lease=self.activate(child)
        for operation in (
                self.x.control.prepare,
                lambda:self.x.control.activate(self.grant_ab),
                lambda:self.x.control.claim_writer(expected_epoch=1,owner_id=str(uuid4())),
                lambda:self.x.control.open_writer(self.lease_ab)):
            with self.subTest(operation=operation),self.assertRaises(PermissionError):
                operation()
        self.assert_fenced(self.writer_b)
        status=self.x.control.status()
        self.assertEqual(status["phase"],"retired")
        with sqlite3.connect(self.writer_b._path) as db:
            self.assertEqual(db.execute("SELECT envelope FROM writer_enrollment").fetchone()[0],enrollment)
        self.assertEqual(self.observe_child(child,child["control"].open_writer(lease))["revision"],2)

    def test_parent_epoch_change_invalidates_prepared_continuation_intent(self):
        child=self.child("stale-parent")
        replacement=self.x.control.claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        with self.assertRaises(PermissionError):
            child["control"].prepare()
        self.assert_fenced(child["ledger"])
        self.assertEqual(self.x.control.status()["phase"],"active")
        self.assertEqual(self.x.observe(self.x.control.open_writer(replacement))["accepted_events"],1)

    def test_retired_parent_rejects_ingest_and_operator_acknowledgement(self):
        self.x.observe(self.writer_b,"integrity_failure")
        report=self.writer_b.report()
        child=self.child("mutation")
        self.activate(child)
        eb=event_bindings(self.writer_b._id,report["accepted_events"]+1,"tool_denied")
        ea=self.x.f.sign(self.x.r.sensor,EVENT_CLAIM,eb,self.x.f.now,"artifact-integrity")
        rb=review_bindings(self.writer_b._id,report["revision"],report["state_sha256"])
        ra=self.x.f.sign(self.x.r.operator,REVIEW_CLAIM,rb,self.x.f.now,"independent-reproduction")
        with self.assertRaises(PermissionError):
            self.writer_b.ingest(eb,ea)
        with self.assertRaises(PermissionError):
            self.writer_b.acknowledge(rb,ra)
        self.assertEqual(self.writer_b.report(),report)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_competing_continuations_have_one_retirement_destination(self):
        candidates={label:self.child(label) for label in ("left","right")}
        ctx=multiprocessing.get_context("fork")
        start=ctx.Event()
        results=ctx.Queue()
        self.addCleanup(results.close)
        def compete(label):
            start.wait(timeout=5)
            try:
                self.reopen(candidates[label]).prepare()
                results.put(("ready",label))
            except PermissionError:
                results.put(("fenced",label))
        children=[self.process(ctx,lambda label=label:compete(label)) for label in candidates]
        start.set()
        outcomes=[results.get(timeout=10),results.get(timeout=10)]
        for process in children:
            self.join(process)
        self.assertEqual(sorted(result[0] for result in outcomes),["fenced","ready"])
        winning=next(candidates[label] for status,label in outcomes if status=="ready")
        losing=next(candidates[label] for status,label in outcomes if status=="fenced")
        self.assert_fenced(self.writer_b)
        self.assert_fenced(losing["ledger"])
        with self.assertRaises(PermissionError):
            self.reopen(losing).prepare()
        lease=self.activate(winning)
        self.assertEqual(self.observe_child(winning,self.reopen(winning).open_writer(lease))["revision"],2)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_process_exit_after_parent_retirement_resumes_child_intent(self):
        child=self.child("retirement-crash")
        ctx=multiprocessing.get_context("fork")
        def crash():
            control=self.reopen(child)
            original=handover._control_transaction
            @contextmanager
            def stop_after_retirement(path):
                retired=False
                with original(path) as db:
                    yield db
                    if Path(path)==self.x.control._path:
                        retired=self.x.control._read(db)["phase"]=="retired"
                if retired:
                    os._exit(81)
            handover._control_transaction=stop_after_retirement
            control.prepare()
            os._exit(1)
        process=self.process(ctx,crash)
        self.join(process,81)
        self.assertEqual(self.x.control.status()["phase"],"retired")
        self.assert_fenced(self.writer_b)
        self.assert_fenced(child["ledger"])
        self.assertEqual(self.reopen(child).status()["phase"],"preparing")
        lease=self.activate(child)
        self.assertEqual(self.observe_child(child,self.reopen(child).open_writer(lease))["accepted_events"],1)

    def test_open_writer_uses_latest_anchor_to_reject_restored_old_ledger(self):
        # Ownership did not change; a newly retained independent anchor must
        # still constrain this already-open object before its signer runs.
        original=self.writer_b._path.read_bytes()
        self.x.observe(self.writer_b)
        self.x.r.anchor()
        self.writer_b._path.write_bytes(original)
        self.assert_fenced(self.writer_b)

    def test_writer_rejects_missing_or_same_config_copied_custody(self):
        raw=SecurityLedger(self.writer_b._path,ledger_id=self.x.r.new_id,
            requester_id="fixture-worker",clock=lambda:self.x.f.now,
            writer_lease=self.lease_ab,**self.x.r.new_options)
        self.assert_fenced(raw)
        cloned=self.root/"copied-custody"
        cloned.mkdir(mode=0o700)
        shutil.copyfile(self.x.r.successor._path,cloned/"anchor-receipts.sqlite3")
        (cloned/"anchor-receipts.sqlite3").chmod(0o600)
        custody=AnchorCustody(cloned,ledger_id=self.x.r.new_id,trust=self.x.r.anchorer.trust,
            requester_id="fixture-worker",clock=lambda:self.x.f.now)
        self.assertEqual(custody._config,self.x.r.successor._config)
        original=self.writer_b._writer_custody
        self.writer_b._writer_custody=custody
        self.assert_fenced(self.writer_b)
        self.writer_b._writer_custody=original
        self.assertEqual(self.x.observe(self.writer_b)["accepted_events"],1)

    def test_current_custody_renewal_reaches_already_open_writer(self):
        self.x.f.now+=86401
        self.assert_fenced(self.writer_b)
        self.x.r.anchor()
        self.assertEqual(self.x.observe(self.writer_b)["accepted_events"],1)

    def test_nonadjacent_segment_identity_and_key_reuse_are_rejected(self):
        original=self.x.f.options
        candidates=(
            ("reused-id",{"successor_id":original["ledger_id"]}),
            ("reused-key",{"successor_options":{"master_key":original["master_key"]}}),
            ("reused-key-id",{"successor_options":{"key_id":original["key_id"]}}),
        )
        for label,options in candidates:
            with self.subTest(label=label),self.assertRaises(PermissionError):
                self.child(label,**options)
            self.assertFalse((self.root/(label+"-control")/"writer-control.sqlite3").exists())
        self.assertEqual(self.x.observe(self.writer_b)["accepted_events"],1)

    def test_control_cannot_be_created_inside_an_ancestor_archive(self):
        archive=self.x.r.a.directory
        before={path.name:path.read_bytes() for path in archive.iterdir()}
        with self.assertRaises(PermissionError):
            self.child("ancestor-archive",control_directory=archive)
        self.assertEqual({path.name:path.read_bytes() for path in archive.iterdir()},before)
        self.assertFalse((archive/"writer-control.sqlite3").exists())
        self.assertEqual(self.x.observe(self.writer_b)["accepted_events"],1)

    def test_control_cannot_share_ancestor_ledger_or_custody_directory(self):
        protected=(self.x.f.path,self.x.r.a.custody._path)
        before={path:path.read_bytes() for path in protected}
        for label,directory in (("ancestor-ledger",self.x.f.path.parent),
                                ("ancestor-custody",self.x.r.a.custody._directory)):
            with self.subTest(label=label),self.assertRaises(PermissionError):
                self.child(label,control_directory=directory)
            self.assertFalse((directory/"writer-control.sqlite3").exists())
        self.assertEqual({path:path.read_bytes() for path in protected},before)
        self.assertEqual(self.x.observe(self.writer_b)["accepted_events"],1)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_parent_restart_and_continuation_serialize_without_two_winners(self):
        child=self.child("restart-race")
        ctx=multiprocessing.get_context("fork")
        start=ctx.Event()
        results=ctx.Queue()
        self.addCleanup(results.close)
        def restart():
            start.wait(timeout=5)
            try:
                lease=self.x.reopen().claim_writer(expected_epoch=1,owner_id=str(uuid4()))
                results.put(("restart-won",lease))
            except PermissionError:
                results.put(("restart-fenced",None))
        def prepare():
            start.wait(timeout=5)
            try:
                self.reopen(child).prepare()
                results.put(("continuation-won",None))
            except PermissionError:
                results.put(("continuation-fenced",None))
        processes=[self.process(ctx,restart),self.process(ctx,prepare)]
        start.set()
        outcomes=[results.get(timeout=10),results.get(timeout=10)]
        for process in processes:
            self.join(process)
        labels={label for label,_ in outcomes}
        self.assertIn(labels,({"restart-won","continuation-fenced"},
                             {"restart-fenced","continuation-won"}))
        if "restart-won" in labels:
            lease=next(lease for label,lease in outcomes if label=="restart-won")
            self.assertEqual(self.x.observe(self.x.control.open_writer(lease))["accepted_events"],1)
        else:
            self.assert_fenced(self.writer_b)
            lease=self.activate(child)
            self.assertEqual(self.observe_child(child,self.reopen(child).open_writer(lease))["accepted_events"],1)

    @unittest.skipUnless(FORK_AVAILABLE,"requires local fork-capable process isolation")
    def test_custody_lock_spans_signer_and_ledger_commit(self):
        receipt=self.x.r.successor.latest()
        ctx=multiprocessing.get_context("fork")
        signer_entered=ctx.Event()
        release=ctx.Event()
        retain_start=ctx.Event()
        retain_entered=ctx.Event()
        outcomes=ctx.Queue()
        retained=ctx.Queue()
        self.addCleanup(outcomes.close)
        self.addCleanup(retained.close)
        def write():
            writer=self.x.reopen().open_writer(self.lease_ab)
            def sign(binding,now):
                signer_entered.set()
                if not release.wait(timeout=5):
                    raise TimeoutError("custody signer release budget")
                return self.x.f.sign(self.x.r.sensor,EVENT_CLAIM,binding,now,"artifact-integrity")
            outcomes.put(writer.observe_local(SecurityEvent("tool_denied","demo","synthetic"),sign))
        def retain():
            retain_start.wait(timeout=5)
            retain_entered.set()
            self.x.r.successor.retain(receipt)
            retained.put(self.x.r.ledger().report()["revision"])
        # Both forks precede taking either SQLite lock.
        retainer=self.process(ctx,retain)
        writer=self.process(ctx,write)
        self.addCleanup(release.set)
        self.assertTrue(signer_entered.wait(timeout=5))
        retain_start.set()
        self.assertTrue(retain_entered.wait(timeout=5))
        try:
            with self.assertRaises(Empty):
                retained.get(timeout=0.2)
        finally:
            release.set()
        accepted=outcomes.get(timeout=10)
        revision_seen=retained.get(timeout=10)
        self.join(writer)
        self.join(retainer)
        self.assertEqual(accepted["revision"],2)
        self.assertEqual(revision_seen,2)


if __name__=="__main__":
    unittest.main()
