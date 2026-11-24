"""Synthetic recovery receipts and verified encrypted copies.

The custodian stores public signed receipts, never private signing or ledger
keys. Independent OS/storage custody must be supplied by the operator.
Quiesced offline recovery only. No automatic restoration or activation.
"""
from contextlib import contextmanager,closing
from copy import deepcopy
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
from time import time,monotonic

from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .security_ledger import SecurityLedger,ANCHOR_CLAIM,anchor_bindings,_uuid

MAX_RECEIPT=32768
MAX_DB=64*1024*1024

def private_directory(path):
    p=Path(path)
    if not p.is_absolute() or p.resolve()!=p:
        raise PermissionError("canonical absolute private directory required")
    info=p.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise PermissionError("owner-only directory required")
    return p

def private_database(path):
    p=Path(path)
    private_directory(p.parent)
    if p.resolve()!=p or p.is_symlink():
        raise PermissionError("canonical database required")
    info=p.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid()
            or info.st_mode&0o077 or info.st_nlink!=1 or not 0<info.st_size<=MAX_DB):
        raise PermissionError("bounded owner-only regular database required")
    return p

def sync_directory(p):
    fd=os.open(p,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

class AnchorCustody:
    """Retain a monotone latest signed receipt under separately managed storage.

    Not an independent service merely by instantiation. The owner is trusted;
    deletion or rollback of this database itself is outside the guarantees.
    """
    def __init__(self,directory,*,ledger_id,trust,requester_id,clock=time,create=False):
        self._directory=private_directory(directory)
        self._path=self._directory/"anchor-receipts.sqlite3"
        self._id=_uuid(ledger_id)
        if type(trust) is not dict or not 1<=len(trust)<=16 or not requester_id or not callable(clock):
            raise ValueError("pinned custodian configuration required")
        if type(create) is not bool:
            raise ValueError("explicit creation flag required")
        self._trust=deepcopy(trust)
        self._requester=requester_id
        self._clock=clock
        self._config=digest({"ledger_id":self._id,"trust":self._trust,"requester":requester_id})
        if create:
            fd=os.open(self._path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            os.close(fd)
            with closing(sqlite3.connect(self._path)) as db,db:
                db.execute("PRAGMA synchronous=FULL")
                db.execute("CREATE TABLE custody (slot INTEGER PRIMARY KEY CHECK(slot=1), config TEXT NOT NULL, receipt BLOB)")
                db.execute("INSERT INTO custody VALUES(1,?,NULL)",(self._config,))
            sync_directory(self._directory)
        with self._transaction() as db:
            self._read(db,allow_empty=True)

    @contextmanager
    def _transaction(self):
        private_database(self._path)
        with closing(sqlite3.connect(self._path.as_uri()+"?mode=rw",uri=True,timeout=5)) as db:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def _verify(self,receipt,*,fresh):
        if type(receipt) is not dict or set(receipt)!={"bindings","attestation"}:
            raise ValueError("exact signed anchor required")
        encoded=canonical(receipt)
        if len(encoded)>MAX_RECEIPT:
            raise ValueError("receipt size exceeded")
        b=receipt["bindings"]
        if type(b) is not dict:
            raise ValueError("anchor binding required")
        expected=anchor_bindings(self._id,b.get("revision"),b.get("state_sha256"))
        if canonical(b)!=canonical(expected):
            raise PermissionError("anchor subject differs")
        now=datetime.fromtimestamp(self._clock(),timezone.utc)
        if not fresh:
            issued=datetime.strptime(receipt["attestation"]["statement"]["created_at_utc"],
                                     "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if issued>now:
                raise PermissionError("anchor issued in future")
            now=issued
        fresh_attestation(receipt["attestation"],trust=self._trust,claim_id=ANCHOR_CLAIM,
            bundle_sha256=digest(expected),bindings=expected,requester_id=self._requester,
            purpose="independent-reproduction",now=now,max_age_seconds=86400)
        return encoded

    def _read(self,db,*,allow_empty=False):
        rows=db.execute("SELECT slot,config,length(receipt) FROM custody").fetchall()
        if len(rows)!=1 or rows[0][:2]!=(1,self._config):
            raise PermissionError("custody identity differs")
        size=rows[0][2]
        if size is None:
            if allow_empty:
                return None
            raise PermissionError("no retained anchor")
        if type(size) is not int or not 1<=size<=MAX_RECEIPT:
            raise ValueError("invalid stored receipt size")
        raw=db.execute("SELECT receipt FROM custody WHERE slot=1").fetchone()[0]
        receipt=json.loads(raw)
        if self._verify(receipt,fresh=False)!=raw:
            raise ValueError("stored receipt not canonical")
        return receipt

    def retain(self,receipt):
        receipt=deepcopy(receipt)
        encoded=self._verify(receipt,fresh=True)
        b=receipt["bindings"]
        with self._transaction() as db:
            old=self._read(db,allow_empty=True)
            if old is not None:
                previous=old["bindings"]
                if b["revision"]<previous["revision"]:
                    raise PermissionError("retained revision cannot decrease")
                if b["revision"]==previous["revision"]:
                    if b!=previous:
                        raise PermissionError("conflicting same-revision anchor")
                    if canonical(old)==encoded:
                        return b["revision"]
                if receipt["attestation"]["statement"]["created_at_utc"]<old["attestation"]["statement"]["created_at_utc"]:
                    raise PermissionError("anchor timestamp regressed")
            db.execute("UPDATE custody SET receipt=? WHERE slot=1",(encoded,))
            return b["revision"]

    def latest(self):
        with self._transaction() as db:
            receipt=self._read(db)
            self._verify(receipt,fresh=True)
            return receipt

    def open_ledger(self,path,*,master_key,key_id,sensor_keys,operator_keys):
        private_database(path)
        separated_trust(sensor_keys,self._trust)
        separated_trust(operator_keys,self._trust)
        anchor=self.latest()
        return SecurityLedger(path,ledger_id=self._id,master_key=master_key,key_id=key_id,
            sensor_keys=sensor_keys,operator_keys=operator_keys,requester_id=self._requester,
            clock=self._clock,anchor_keys=self._trust,anchor=anchor,
            min_revision=anchor["bindings"]["revision"])

def verified_recovery_copy(source,destination,*,custody,master_key,key_id,sensor_keys,operator_keys):
    """Verify exact anchored encrypted backup and publish without overwriting.

    The operator must stop writers and keep custody available throughout.
    The new copy is not authorized to become an active writer.
    """
    if type(custody) is not AnchorCustody:
        raise TypeError("configured anchor custody required")
    source=private_database(source)
    target=Path(destination)
    parent=private_directory(target.parent)
    if target.resolve()!=target or target.exists() or target.is_symlink():
        raise FileExistsError("new canonical destination required")
    if len({source.parent,parent,custody._directory})!=3:
        raise PermissionError("distinct source, custody and recovery directories required")
    options=dict(master_key=master_key,key_id=key_id,sensor_keys=sensor_keys,operator_keys=operator_keys)
    before=custody.latest()["bindings"]
    def exact(report):
        if report["revision"]!=before["revision"] or report["state_sha256"]!=before["state_sha256"]:
            raise PermissionError("recovery requires exact retained anchor")
    exact(custody.open_ledger(source,**options).report())
    started=monotonic()
    with tempfile.TemporaryDirectory(prefix=".verified-recovery-",dir=parent) as folder:
        temp=Path(folder)/"encrypted.sqlite3"
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        os.close(fd)
        with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True,timeout=5)) as src,closing(sqlite3.connect(temp,timeout=5)) as dst:
            page_size=src.execute("PRAGMA page_size").fetchone()[0]
            def progress(status,remaining,total):
                if monotonic()-started>20 or total*page_size>MAX_DB:
                    raise TimeoutError("recovery budget exceeded")
            src.backup(dst,pages=128,progress=progress,sleep=0.01)
        restored=custody.open_ledger(temp,**options).report()
        exact(restored)
        exact(custody.open_ledger(source,**options).report())
        # Serialize against receipt updates while publishing the verified copy.
        with custody._transaction() as db:
            latest=custody._read(db)
            custody._verify(latest,fresh=True)
            if latest["bindings"]!=before:
                raise PermissionError("custodian tip changed during recovery")
            with temp.open("rb") as stream:
                os.fsync(stream.fileno())
            os.link(temp,target,follow_symlinks=False)
            temp.unlink()
            sync_directory(parent)
    return {"schema":"wilborn-verified-recovery/1","data_class":"synthetic",
            "revision":restored["revision"],"state_sha256":restored["state_sha256"],
            "encrypted_copy_verified":True,"anchor_verified":True,"original_replaced":False,
            "execution_authorized":False,"production_qualified":False}
