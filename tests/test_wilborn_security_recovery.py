"""Bounded synthetic backup and custody checks."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import sqlite3
import unittest

import test_wilborn_security_history as fixtures
from wilborn_ops.security_ledger import ANCHOR_CLAIM,anchor_bindings
from wilborn_ops.security_recovery import AnchorCustody,verified_recovery_copy

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.HistoryTests()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.root=Path(self.f.temp.name).resolve()
        self.custody_dir=self.root/"custody"
        self.restore_dir=self.root/"recovery"
        self.custody_dir.mkdir(mode=0o700)
        self.restore_dir.mkdir(mode=0o700)
        self.custody=self.open_custody(create=True)
        self.options={k:self.f.options[k] for k in ("master_key","key_id","sensor_keys","operator_keys")}
        self.target=self.restore_dir/"restored.sqlite3"

    def open_custody(self,**kw):
        return AnchorCustody(self.custody_dir,ledger_id=self.f.options["ledger_id"],
            trust=self.f.anchorer.trust,requester_id=self.f.options["requester_id"],
            clock=lambda:self.f.now,**kw)

    def copy(self,source=None,target=None,**kw):
        return verified_recovery_copy(source or self.f.path,target or self.target,
            custody=self.open_custody(),**{**self.options,**kw})

    def test_persistent_monotone_custody_and_renewal(self):
        with self.assertRaises(PermissionError):
            self.custody.latest()
        self.f.observe("auth_failure")
        first=self.f.anchor()
        self.assertEqual(self.custody.retain(first),2)
        self.assertEqual(self.open_custody().latest(),first)
        self.f.observe("integrity_failure")
        latest=self.f.anchor()
        self.custody.retain(latest)
        with self.assertRaises(PermissionError):
            self.open_custody().retain(first)
        b=anchor_bindings(self.f.options["ledger_id"],3,"a"*64)
        conflict={"bindings":b,"attestation":self.f.sign(self.f.anchorer,ANCHOR_CLAIM,b,
            self.f.now,"independent-reproduction")}
        with self.assertRaises(PermissionError):
            self.custody.retain(conflict)
        self.f.now+=86401
        with self.assertRaises(PermissionError):
            self.open_custody().latest()
        renewed=self.f.anchor()
        self.custody.retain(renewed)
        self.assertEqual(self.open_custody().latest(),renewed)

    def test_verified_copy_preserves_history_and_no_clobber(self):
        self.f.observe("auth_failure")
        self.f.observe("integrity_failure")
        self.custody.retain(self.f.anchor())
        expected=self.f.ledger.report()
        result=self.copy()
        self.assertTrue(result["encrypted_copy_verified"])
        self.assertEqual(result["state_sha256"],expected["state_sha256"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["production_qualified"])
        recovered=self.open_custody().open_ledger(self.target,**self.options)
        self.assertEqual(recovered.history(),self.f.ledger.history())
        self.assertEqual(self.f.ledger.report(),expected)
        with self.assertRaises(FileExistsError):
            self.copy()
        self.assertEqual(recovered.report()["revision"],3)

    def test_older_or_unanchored_copy_rejected(self):
        self.f.observe("auth_failure")
        old=self.root/"older.sqlite3"
        fd=os.open(old,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(fd)
        with sqlite3.connect(self.f.path) as src,sqlite3.connect(old) as dst:
            src.backup(dst)
        self.f.observe("integrity_failure")
        self.custody.retain(self.f.anchor())
        with self.assertRaises(PermissionError):
            self.copy(source=old)
        self.f.observe("tool_denied")
        with self.assertRaises(PermissionError):
            self.copy()
        self.assertFalse(self.target.exists())

    def test_wrong_signer_and_concurrent_retry(self):
        self.f.observe("auth_failure")
        anchor=self.f.anchor()
        bad={"bindings":anchor["bindings"],"attestation":self.f.sign(self.f.sensor,ANCHOR_CLAIM,
            anchor["bindings"],self.f.now,"independent-reproduction")}
        with self.assertRaises(ValueError):
            self.custody.retain(bad)
        workers=[self.open_custody() for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(list(pool.map(lambda w:w.retain(anchor),workers)),[2]*4)
        self.assertEqual(self.open_custody().latest(),anchor)

    def test_invalid_storage_and_wrong_key_rejected(self):
        self.f.observe("auth_failure")
        self.custody.retain(self.f.anchor())
        with self.assertRaises(PermissionError):
            self.copy(master_key=os.urandom(32))
        with self.assertRaises(PermissionError):
            self.copy(target=self.root/"same-directory.sqlite3")
        self.restore_dir.chmod(0o755)
        with self.assertRaises(PermissionError):
            self.copy()
        self.assertFalse(self.target.exists())
        with sqlite3.connect(self.custody_dir/"anchor-receipts.sqlite3") as db:
            db.execute("UPDATE custody SET receipt=?",(b"{}",))
        with self.assertRaises(ValueError):
            self.open_custody()
