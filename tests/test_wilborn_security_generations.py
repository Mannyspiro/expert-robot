"""Bounded real multi-generation lineage with synthetic keys/events only."""
from copy import deepcopy
import os
import sqlite3
import unittest
from uuid import uuid4

import test_wilborn_security_handover as fixtures
from test_wilborn_attested_integration import Signer
from wilborn_ops.security_archive import ARCHIVE_CLAIM,stage_archive,seal_archive
from wilborn_ops.security_handover import WriterHandover,CLAIM,MAX_HANDOVERS
from wilborn_ops.security_ledger import SecurityLedger,MAX_HISTORY,ANCHOR_CLAIM,EVENT_CLAIM,anchor_bindings
from wilborn_ops.security_monitor import SecurityEvent
from wilborn_ops.security_recovery import AnchorCustody
from wilborn_ops.security_rotation import CLAIM as ROTATION_CLAIM,stage_rotation,seal_rotation


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.x=fixtures.HandoverTests()
        self.addCleanup(self.x.doCleanups)
        self.x.setUp()
        self.f=self.x.f
        self.root=self.x.r.a.fixture.root
        first=self.x.control
        lease=self.x.activate()
        self.generations=[dict(control=first,lease=lease,writer=first.open_writer(lease),
            sensor=self.x.r.sensor,operator=self.x.r.operator,anchorer=self.x.r.anchorer,
            reviewer=self.x.reviewer,kwargs=self.x.kwargs,directory=self.x.directory)]

    def observe(self,generation,kind="integrity_failure"):
        return generation["writer"].observe_local(SecurityEvent(kind,"demo","synthetic"),
            lambda b,now:self.f.sign(generation["sensor"],EVENT_CLAIM,b,now,"artifact-integrity"))

    def anchor(self,generation):
        control=generation["control"]
        report=control._ledger("successor").report()
        b=anchor_bindings(control._new._id,report["revision"],report["state_sha256"])
        control._new.retain({"bindings":b,"attestation":self.f.sign(generation["anchorer"],
            ANCHOR_CLAIM,b,self.f.now,"independent-reproduction")})

    def extend(self,*,events=("integrity_failure",),label=None,overrides=None):
        previous=self.generations[-1]
        for kind in events:
            self.observe(previous,kind)
        self.anchor(previous)
        parent=previous["control"]
        label=label or "generation-"+str(len(self.generations)+1)
        archive=self.root/(label+"-archive")
        archive_reviewer=Signer(label+"-archive-reviewer")
        staged=stage_archive(parent._target,archive,custody=parent._new,options=parent._new_options)
        seal_archive(archive,custody=parent._new,options=parent._new_options,
            reviewer_keys=archive_reviewer.trust,review_attestation=self.f.sign(archive_reviewer,
            ARCHIVE_CLAIM,staged["review_bindings"],self.f.now,"independent-reproduction"))
        sensor,operator,anchorer,rotation_reviewer,reviewer=(Signer(label+"-"+role)
            for role in ("sensor","operator","anchor","rotation-reviewer","handover-reviewer"))
        custody_dir=self.root/(label+"-custody")
        custody_dir.mkdir(mode=0o700)
        custody=AnchorCustody(custody_dir,ledger_id=str(uuid4()),trust=anchorer.trust,
            requester_id="fixture-worker",clock=lambda:self.f.now,create=True)
        options=dict(master_key=os.urandom(32),key_id=label+"-key",
                     sensor_keys=sensor.trust,operator_keys=operator.trust)
        stage=self.root/(label+"-stage")
        rotation=dict(predecessor=parent._new,successor=custody,old_options=parent._new_options,
            new_options=options,archive_review_keys=archive_reviewer.trust,
            reserve_revisions=MAX_HISTORY-parent._ledger("successor").report()["revision"])
        rotated=stage_rotation(parent._target,archive,stage,**rotation)
        ledger=SecurityLedger(stage/"successor.sqlite3",ledger_id=custody._id,
            requester_id="fixture-worker",clock=lambda:self.f.now,**options)
        report=ledger.report()
        b=anchor_bindings(custody._id,report["revision"],report["state_sha256"])
        custody.retain({"bindings":b,"attestation":self.f.sign(anchorer,ANCHOR_CLAIM,b,
                                                               self.f.now,"independent-reproduction")})
        seal_rotation(parent._target,archive,stage,**rotation,
            rotation_review_keys=rotation_reviewer.trust,
            review_attestation=self.f.sign(rotation_reviewer,ROTATION_CLAIM,
                rotated["review_bindings"],self.f.now,"independent-reproduction"))
        directory=self.root/(label+"-control")
        directory.mkdir(mode=0o700)
        kwargs=dict(handover_id=str(uuid4()),source=parent._target,archive=archive,stage=stage,
            **rotation,rotation_review_keys=rotation_reviewer.trust,handover_review_keys=reviewer.trust,
            previous=parent)
        kwargs.update(overrides or {})
        control=WriterHandover(directory,**kwargs,create=True,owner_id=str(uuid4()))
        binding=control.prepare()
        grant=self.f.sign(reviewer,CLAIM,binding,self.f.now,"independent-reproduction")
        lease=control.activate(grant)
        result=dict(control=control,lease=lease,writer=control.open_writer(lease),sensor=sensor,
            operator=operator,anchorer=anchorer,reviewer=reviewer,kwargs=kwargs,directory=directory)
        self.generations.append(result)
        return result

    def test_three_transfers_reopen_complete_chain_and_preserve_incidents(self):
        first=self.generations[0]
        second=self.extend(events=("tool_denied","integrity_failure"))
        third=self.extend(events=("auth_failure","integrity_failure"))
        self.observe(third,"provenance_rejected")
        current=WriterHandover(third["directory"],**third["kwargs"])
        lease=current.claim_writer(expected_epoch=1,owner_id=str(uuid4()))
        third["writer"]=current.open_writer(lease)
        self.observe(third,"tool_denied")
        snapshot=current.lineage_snapshot()
        self.assertEqual(snapshot["ownership_epoch"],2)
        self.assertEqual(len(snapshot["segments"]),4)
        reports=[r for r,_ in snapshot["segments"]]
        self.assertEqual([r["accepted_events"] for r in reports],[2,2,2,2])
        self.assertEqual([r["pending_alerts"] for r in reports],
            [{"integrity_failure":1}]*3+[{"provenance_rejected":1}])
        self.assertEqual([r["revision"] for r in reports],[3,3,3,3])
        for item in (first,second):
            self.assertEqual(item["control"].status()["phase"],"retired")
            with self.assertRaises(PermissionError):
                self.observe(item)
            with self.assertRaises(PermissionError):
                item["control"].lineage_snapshot()

    def test_eight_segment_policy_bound_rejects_ninth_without_retiring_owner(self):
        for _ in range(MAX_HANDOVERS-1):
            self.extend()
        current=self.generations[-1]
        before=current["control"].lineage_snapshot()
        self.assertEqual(len(before["segments"]),8)
        from wilborn_ops.security_dashboard import studio_lineage_snapshot
        exported=studio_lineage_snapshot(current["control"])
        self.assertEqual(len(exported["segments"]),8)
        self.assertEqual(exported["active_segment_index"],7)
        with self.assertRaises(PermissionError):
            self.extend(events=(),label="over-bound")
        self.assertEqual(current["control"].status()["phase"],"active")
        self.assertEqual(self.observe(current)["accepted_events"],1)

    def test_missing_reordered_and_cyclic_ancestry_are_rejected(self):
        second=self.extend()
        third=self.extend()
        with self.assertRaises(PermissionError):
            WriterHandover(third["directory"],**{**third["kwargs"],"previous":None})
        with self.assertRaises(PermissionError):
            WriterHandover(third["directory"],**{**third["kwargs"],"previous":self.generations[0]["control"]})
        old=third["control"]._previous
        try:
            third["control"]._previous=third["control"]
            with self.assertRaises(PermissionError):
                third["control"].lineage_snapshot()
        finally:
            third["control"]._previous=old
        self.assertEqual(len(third["control"].lineage_snapshot()["segments"]),4)

    def test_corrupt_earliest_proof_blocks_latest_recovery_and_view(self):
        second=self.extend()
        third=self.extend()
        path=self.generations[0]["control"]._stage/"continuity.json"
        original=path.read_bytes()
        path.write_bytes(b"{}")
        for call in (third["control"].lineage_snapshot,
                     lambda:third["control"].claim_writer(expected_epoch=1,owner_id=str(uuid4()))):
            with self.assertRaises((PermissionError,ValueError)):
                call()
        path.write_bytes(original)
        self.assertEqual(third["control"].status()["epoch"],1)

    def test_authenticated_retirement_destination_cannot_be_substituted(self):
        second=self.extend()
        first=self.generations[0]["control"]
        with handover_transaction(first) as (db,state):
            state["retirement"]["next"]["handover_id"]=str(uuid4())
            first._save(db,state)
        with self.assertRaises(PermissionError):
            second["control"].lineage_snapshot()

    def test_legacy_custody_unbound_grant_requires_reviewed_continuation(self):
        first=self.generations[0]
        control=first["control"]
        # Reconstruct the previous published plan shape and a valid fixture
        # signature for it. This is historical-format compatibility evidence.
        with handover_transaction(control) as (db,state):
            del state["plan"]["predecessor_custody"]
            del state["plan"]["successor_custody"]
            state["attestation"]=self.f.sign(first["reviewer"],CLAIM,control._binding(state),
                                             self.f.now,"independent-reproduction")
            control._save(db,state)
        self.assertEqual(control.status()["phase"],"active")
        with self.assertRaises(PermissionError):
            control.open_writer(first["lease"])
        with self.assertRaises(PermissionError):
            self.observe(first)
        migrated=self.extend(events=())
        self.assertEqual(self.observe(migrated)["accepted_events"],1)
        self.assertEqual(control.status()["phase"],"retired")


def handover_transaction(control):
    """Host-key fault injection only; no altered receipt is treated as verified."""
    from contextlib import contextmanager
    from wilborn_ops.security_handover import _control_transaction
    @contextmanager
    def opened():
        with _control_transaction(control._path) as db:
            yield db,deepcopy(control._read(db))
    return opened()


if __name__=="__main__":
    unittest.main()
