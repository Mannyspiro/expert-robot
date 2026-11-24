"""Encrypted synthetic security checkpoint with signed sensor/operator roles.

Local trusted host only; no network, upstream ARTEX runtime, raw logs, or
production data. One ordered sensor stream per ledger. SQLite transactions
serialize writers across processes. Whole-file rollback and compromised host
or sensor are outside the guarantees; use external revision anchors in a
separately qualified production design.
"""
from collections import deque
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from time import time
from uuid import UUID

from python.merlin.artifact_ref import ArtifactRef
from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .security_monitor import KINDS,REVIEW_KINDS,RULES,MAX_COUNTER,SecurityEvent
from .security_monitor import active_windows,advance_windows,expire_windows
from .titan_envelope import seal_demo,open_demo

EVENT_CLAIM="wilborn:security:sensor-event:v1"
REVIEW_CLAIM="wilborn:security:operator-review:v1"
SCHEMA="wilborn-encrypted-security-checkpoint/1"
MAX_CLOCK=253402300799
MAX_ENVELOPE=32768
ALERTS=frozenset(REVIEW_KINDS)|frozenset(RULES)

def _uuid(value):
    if type(value) is not str:
        raise ValueError("canonical ledger UUID required")
    try:
        parsed=UUID(value)
    except ValueError:
        raise ValueError("canonical ledger UUID required") from None
    if str(parsed)!=value or parsed.version!=4:
        raise ValueError("canonical v4 ledger UUID required")
    return value

def _integer(value,minimum=0,maximum=MAX_COUNTER):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError("bounded integer required")
    return value

def _hex(value):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}",value):
        raise ValueError("digest required")
    return value

def event_bindings(ledger_id,sequence,kind):
    SecurityEvent(kind,"demo","synthetic")
    return {"schema":"wilborn-security-event/1","environment":"demo",
            "data_class":"synthetic","ledger_id":_uuid(ledger_id),
            "sequence":_integer(sequence,1),"kind":kind}

def review_bindings(ledger_id,revision,state_sha256):
    return {"schema":"wilborn-security-review/1","environment":"demo",
            "data_class":"synthetic","ledger_id":_uuid(ledger_id),
            "revision":_integer(revision,1),"state_sha256":_hex(state_sha256),
            "decision":"acknowledge_pending_alerts","execution_authorized":False}

def _counts(values,allowed):
    if type(values) is not dict or not set(values)<=allowed:
        raise ValueError("invalid checkpoint counters")
    for count in values.values():
        _integer(count,1)
    return values

class SecurityLedger:
    def __init__(self,path,*,ledger_id,master_key,key_id,sensor_keys,operator_keys,
                 requester_id,create=False,clock=time,min_revision=1):
        self._id=_uuid(ledger_id)
        self._min_revision=_integer(min_revision,1)
        if type(master_key) is not bytes or len(master_key)!=32:
            raise ValueError("trusted host 256-bit key required")
        if type(key_id) is not str or not re.fullmatch("[A-Za-z0-9_.:-]{1,128}",key_id):
            raise ValueError("key identity required")
        if type(sensor_keys) is not dict or len(sensor_keys)!=1 or type(operator_keys) is not dict:
            raise ValueError("one sensor stream and separate operator trust required")
        separated_trust(sensor_keys,operator_keys)
        if (type(requester_id) is not str or not 1<=len(requester_id)<=128
                or not callable(clock) or type(create) is not bool):
            raise ValueError("trusted host configuration required")
        self._path=Path(path).absolute()
        self._key=master_key
        self._key_id=key_id
        self._sensor=deepcopy(sensor_keys)
        self._operators=deepcopy(operator_keys)
        self._requester=requester_id
        self._clock=clock
        # Bind persisted state to host trust configuration. Changing keys requires
        # an explicitly reviewed migration, not silent reset or stream takeover.
        self._config=digest({"sensor":self._sensor,"operators":self._operators,
                             "requester":requester_id,"key_id":key_id})
        if create:
            if self._min_revision!=1:
                raise ValueError("new ledger must start at revision 1")
            fd=os.open(self._path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            os.close(fd)
            with self._transaction() as db:
                db.execute("CREATE TABLE checkpoint (slot INTEGER PRIMARY KEY CHECK(slot=1), revision INTEGER NOT NULL, envelope TEXT NOT NULL)")
                now=self._now()
                initial={"schema":SCHEMA,"ledger_id":self._id,"config_sha256":self._config,
                         "revision":1,"sequence":0,"last_event":None,"last_seen":now,
                         "counts":{},"pending":{},"windows":{name:[] for name in RULES},
                         "reviews":0,"last_review":None,"salt":secrets.token_hex(16)}
                self._save(db,initial,insert=True)
        else:
            # Opening is read/verify only. Never auto-create a missing ledger.
            with self._transaction() as db:
                self._load(db)

    @contextmanager
    def _transaction(self):
        if self._path.is_symlink() or not self._path.is_file():
            raise FileNotFoundError("existing private ledger file required")
        db=sqlite3.connect(self._path.as_uri()+"?mode=rw",uri=True,timeout=5)
        try:
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _now(self,state=None):
        value=self._clock()
        if type(value) not in (int,float) or not 0<=value<=MAX_CLOCK:
            raise ValueError("valid host UTC clock required")
        now=int(value)
        if state is not None and now<state["last_seen"]:
            raise PermissionError("host clock moved backward")
        return now

    def _ref(self,revision,sha):
        return ArtifactRef("wilborn-demo","security/wilborn/synthetic_fixture/"+self._id,
                           _integer(revision,1),_hex(sha)).to_dict()

    def _validate(self,state,revision):
        fields={"schema","ledger_id","config_sha256","revision","sequence","last_event",
                "last_seen","counts","pending","windows","reviews","last_review","salt"}
        if type(state) is not dict or set(state)!=fields or state["schema"]!=SCHEMA:
            raise ValueError("invalid checkpoint schema")
        if state["ledger_id"]!=self._id or state["config_sha256"]!=self._config:
            raise PermissionError("checkpoint host configuration mismatch")
        if _integer(state["revision"],1)!=revision:
            raise ValueError("checkpoint revision mismatch")
        if revision<self._min_revision:
            raise PermissionError("checkpoint older than supplied revision anchor")
        seq=_integer(state["sequence"])
        reviews=_integer(state["reviews"])
        if revision!=1+seq+reviews:
            raise ValueError("checkpoint sequence/review invariant")
        for key,counter in (("last_event",seq),("last_review",reviews)):
            if counter:
                _hex(state[key])
            elif state[key] is not None:
                raise ValueError("unexpected checkpoint identity")
        now=_integer(state["last_seen"],0,MAX_CLOCK)
        counts=_counts(state["counts"],KINDS)
        pending=_counts(state["pending"],ALERTS)
        if sum(counts.values())!=seq or any(v>seq for v in pending.values()):
            raise ValueError("checkpoint event count invariant")
        if type(state["salt"]) is not str or not re.fullmatch("[0-9a-f]{32}",state["salt"]):
            raise ValueError("checkpoint nonce salt invalid")
        if type(state["windows"]) is not dict or set(state["windows"])!=set(RULES):
            raise ValueError("checkpoint windows invalid")
        for name,(_,limit,seconds) in RULES.items():
            w=state["windows"][name]
            if type(w) is not list or len(w)>limit:
                raise ValueError("checkpoint window bound")
            for timestamp in w:
                _integer(timestamp,max(0,now-seconds+1),now)
            if w!=sorted(w):
                raise ValueError("checkpoint window ordering")
        return state

    def _load(self,db):
        rows=db.execute("SELECT revision,length(envelope) FROM checkpoint").fetchall()
        if len(rows)!=1:
            raise RuntimeError("checkpoint missing or invalid")
        revision,length=rows[0]
        _integer(revision,1)
        _integer(length,1,MAX_ENVELOPE)
        raw=db.execute("SELECT envelope FROM checkpoint WHERE slot=1").fetchone()
        if raw is None or type(raw[0]) is not str:
            raise RuntimeError("checkpoint missing")
        envelope=json.loads(raw[0])
        if type(envelope) is not dict:
            raise ValueError("invalid checkpoint envelope")
        embedded=envelope["context"]["artifact_ref"]
        ref=self._ref(revision,embedded["sha256"])
        content=open_demo(envelope,artifact_ref=ref,key_id=self._key_id,master_key=self._key)
        state=json.loads(content)
        if canonical(state)!=content:
            raise ValueError("noncanonical checkpoint")
        return self._validate(state,revision)

    def _save(self,db,state,*,insert=False):
        state["salt"]=secrets.token_hex(16)
        self._validate(state,state["revision"])
        content=canonical(state)
        ref=self._ref(state["revision"],hashlib.sha256(content).hexdigest())
        envelope=canonical(seal_demo(content,artifact_ref=ref,key_id=self._key_id,
                                     master_key=self._key)).decode("utf-8")
        if len(envelope)>MAX_ENVELOPE:
            raise ValueError("checkpoint size limit")
        if insert:
            db.execute("INSERT INTO checkpoint VALUES(1,?,?)",(state["revision"],envelope))
        else:
            changed=db.execute("UPDATE checkpoint SET revision=?,envelope=? WHERE slot=1 AND revision=?",
                               (state["revision"],envelope,state["revision"]-1))
            if changed.rowcount!=1:
                raise RuntimeError("checkpoint revision changed")

    @staticmethod
    def _windows(state):
        return {name:deque(state["windows"][name],maxlen=limit)
                for name,(_,limit,_) in RULES.items()}

    @staticmethod
    def _keep_windows(state,windows,now):
        state["last_seen"]=now
        state["windows"]={name:list(w) for name,w in windows.items()}

    def _report(self,state,now):
        windows=self._windows(state)
        expire_windows(windows,now)
        return {"schema":"wilborn-security-review-report/1","environment":"demo",
                "data_class":"synthetic","ledger_id":self._id,"revision":state["revision"],
                "state_sha256":digest(state),"accepted_events":state["sequence"],
                "counts":dict(sorted(state["counts"].items())),
                "pending_alerts":dict(sorted(state["pending"].items())),
                "active_correlations":active_windows(windows),"operator_reviews":state["reviews"],
                "compromise_confirmed":False,"execution_authorized":False,
                "production_qualified":False}

    def report(self):
        """Host-only report. No keys, raw payloads or sensor/operator names."""
        with self._transaction() as db:
            state=self._load(db)
            return self._report(state,self._now(state))

    def ingest(self,bindings,attestation):
        if type(bindings) is not dict:
            raise TypeError("typed signed event required")
        expected=event_bindings(self._id,bindings.get("sequence"),bindings.get("kind"))
        if canonical(bindings)!=canonical(expected):
            raise PermissionError("event schema or ledger mismatch")
        with self._transaction() as db:
            state=self._load(db)
            now=self._now(state)
            event_digest=digest(expected)
            fresh_attestation(attestation,trust=self._sensor,claim_id=EVENT_CLAIM,
                bundle_sha256=event_digest,bindings=expected,requester_id=self._requester,
                purpose="artifact-integrity",now=datetime.fromtimestamp(now,timezone.utc),max_age_seconds=600)
            sequence=expected["sequence"]
            if sequence==state["sequence"] and state["last_event"]==event_digest:
                return {**self._report(state,now),"duplicate":True}
            if sequence!=state["sequence"]+1:
                raise PermissionError("event sequence gap, conflict or replay")
            if state["revision"]>=MAX_COUNTER:
                raise OverflowError("checkpoint revision exhausted")
            kind=expected["kind"]
            windows=self._windows(state)
            triggered,_=advance_windows(windows,kind,now)
            state["counts"][kind]=state["counts"].get(kind,0)+1
            for alert in sorted(set(triggered)|({kind} if kind in REVIEW_KINDS else set())):
                state["pending"][alert]=state["pending"].get(alert,0)+1
            state["sequence"]=sequence
            state["last_event"]=event_digest
            state["revision"]+=1
            self._keep_windows(state,windows,now)
            self._save(db,state)
            return {**self._report(state,now),"duplicate":False}

    def acknowledge(self,bindings,attestation):
        with self._transaction() as db:
            state=self._load(db)
            now=self._now(state)
            expected=review_bindings(self._id,state["revision"],digest(state))
            if type(bindings) is not dict or canonical(bindings)!=canonical(expected):
                raise PermissionError("operator review is not bound to current checkpoint")
            verified=fresh_attestation(attestation,trust=self._operators,claim_id=REVIEW_CLAIM,
                bundle_sha256=digest(expected),bindings=expected,requester_id=self._requester,
                purpose="independent-reproduction",now=datetime.fromtimestamp(now,timezone.utc),max_age_seconds=600)
            if not state["pending"]:
                raise ValueError("no pending alerts")
            if state["revision"]>=MAX_COUNTER:
                raise OverflowError("checkpoint revision exhausted")
            windows=self._windows(state)
            expire_windows(windows,now)
            state["pending"]={}
            state["reviews"]+=1
            state["last_review"]=verified["statement_sha256"]
            state["revision"]+=1
            self._keep_windows(state,windows,now)
            self._save(db,state)
            return self._report(state,now)
