"""Encrypted synthetic security checkpoint with signed sensor/operator roles.

Local trusted host only; no network, upstream ARTEX runtime, raw logs, or
production data. One ordered sensor stream per ledger. SQLite transactions
serialize writers across processes. Whole-file rollback and compromised host
or sensor are outside the guarantees. A separately supplied signed anchor
can detect rollback behind its exact revision; external custody is not implemented.
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
SCHEMA="wilborn-encrypted-security-checkpoint/2"
ANCHOR_CLAIM="wilborn:security:independent-anchor:v1"
MAX_HISTORY=1024
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

def anchor_bindings(ledger_id,revision,state_sha256):
    return {"schema":"wilborn-security-anchor/1","environment":"demo","data_class":"synthetic",
            "ledger_id":_uuid(ledger_id),"revision":_integer(revision,1,MAX_HISTORY),
            "state_sha256":_hex(state_sha256),"execution_authorized":False}

def _counts(values,allowed):
    if type(values) is not dict or not set(values)<=allowed:
        raise ValueError("invalid checkpoint counters")
    for count in values.values():
        _integer(count,1)
    return values

class SecurityLedger:
    def __init__(self,path,*,ledger_id,master_key,key_id,sensor_keys,operator_keys,
                 requester_id,create=False,clock=time,min_revision=1,anchor_keys=None,anchor=None):
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
        if (anchor_keys is None)!=(anchor is None):
            raise ValueError("anchor and independent trust must be supplied together")
        if anchor is not None:
            separated_trust(sensor_keys,anchor_keys)
            separated_trust(operator_keys,anchor_keys)
        self._anchor_keys=deepcopy(anchor_keys)
        self._anchor=deepcopy(anchor)
        if create and anchor is not None:
            raise ValueError("anchor must refer to an existing checkpoint")
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
                db.execute("CREATE TABLE history (revision INTEGER PRIMARY KEY, envelope TEXT NOT NULL)")
                now=self._now()
                initial={"schema":SCHEMA,"ledger_id":self._id,"config_sha256":self._config,
                         "revision":1,"sequence":0,"last_event":None,"last_seen":now,
                         "counts":{},"pending":{},"windows":{name:[] for name in RULES},
                         "reviews":0,"last_review":None,"salt":secrets.token_hex(16),
                         "previous_sha256":None}
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
                "last_seen","counts","pending","windows","reviews","last_review","salt","previous_sha256"}
        if type(state) is not dict or set(state)!=fields or state["schema"]!=SCHEMA:
            raise ValueError("invalid checkpoint schema")
        if state["ledger_id"]!=self._id or state["config_sha256"]!=self._config:
            raise PermissionError("checkpoint host configuration mismatch")
        if _integer(state["revision"],1)!=revision:
            raise ValueError("checkpoint revision mismatch")
        _integer(revision,1,MAX_HISTORY)
        if revision==1:
            if state["previous_sha256"] is not None:
                raise ValueError("invalid genesis")
        else:
            _hex(state["previous_sha256"])
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

    def _decode_state(self,revision,raw):
        _integer(revision,1,MAX_HISTORY)
        if type(raw) is not str or not 1<=len(raw)<=MAX_ENVELOPE:
            raise ValueError("invalid bounded checkpoint envelope")
        envelope=json.loads(raw)
        if type(envelope) is not dict:
            raise ValueError("invalid checkpoint envelope")
        embedded=envelope["context"]["artifact_ref"]
        ref=self._ref(revision,embedded["sha256"])
        content=open_demo(envelope,artifact_ref=ref,key_id=self._key_id,master_key=self._key)
        state=json.loads(content)
        if canonical(state)!=content:
            raise ValueError("noncanonical checkpoint")
        return self._validate(state,revision)

    def _verified_history(self,db):
        metadata=db.execute("SELECT revision,length(envelope) FROM history ORDER BY revision LIMIT ?",(MAX_HISTORY+1,)).fetchall()
        if not metadata or len(metadata)>MAX_HISTORY:
            raise RuntimeError("missing or oversized incident history")
        states=[]
        previous=None
        for expected,(revision,length) in enumerate(metadata,1):
            if revision!=expected:
                raise PermissionError("incident history gap")
            _integer(length,1,MAX_ENVELOPE)
            raw=db.execute("SELECT envelope FROM history WHERE revision=?",(revision,)).fetchone()[0]
            state=self._decode_state(revision,raw)
            if state["previous_sha256"]!=previous:
                raise PermissionError("incident history chain mismatch")
            previous=digest(state)
            states.append(state)
        return states

    def _check_anchor(self,states):
        if self._anchor is None:
            return 0
        if type(self._anchor) is not dict or set(self._anchor)!={"bindings","attestation"}:
            raise ValueError("exact external anchor required")
        binding=self._anchor["bindings"]
        if type(binding) is not dict:
            raise ValueError("anchor binding required")
        revision=_integer(binding.get("revision"),1,MAX_HISTORY)
        if revision>len(states):
            raise PermissionError("checkpoint older than signed anchor")
        expected=anchor_bindings(self._id,revision,digest(states[revision-1]))
        if canonical(binding)!=canonical(expected):
            raise PermissionError("independent anchor identity mismatch")
        fresh_attestation(self._anchor["attestation"],trust=self._anchor_keys,
            claim_id=ANCHOR_CLAIM,bundle_sha256=digest(expected),bindings=expected,
            requester_id=self._requester,purpose="independent-reproduction",
            now=datetime.fromtimestamp(self._now(states[-1]),timezone.utc),max_age_seconds=86400)
        return revision

    def _load(self,db):
        rows=db.execute("SELECT revision,length(envelope) FROM checkpoint").fetchall()
        if len(rows)!=1:
            raise RuntimeError("checkpoint missing or invalid")
        revision,length=rows[0]
        _integer(revision,1,MAX_HISTORY)
        _integer(length,1,MAX_ENVELOPE)
        if revision<self._min_revision:
            raise PermissionError("checkpoint older than supplied revision anchor")
        raw=db.execute("SELECT envelope FROM checkpoint WHERE slot=1").fetchone()
        if raw is None:
            raise RuntimeError("checkpoint missing")
        state=self._decode_state(revision,raw[0])
        states=self._verified_history(db)
        if len(states)!=revision or digest(states[-1])!=digest(state):
            raise PermissionError("checkpoint and incident history disagree")
        self._check_anchor(states)
        return state

    def _save(self,db,state,*,insert=False):
        state["salt"]=secrets.token_hex(16)
        self._validate(state,state["revision"])
        content=canonical(state)
        ref=self._ref(state["revision"],hashlib.sha256(content).hexdigest())
        envelope=canonical(seal_demo(content,artifact_ref=ref,key_id=self._key_id,
                                     master_key=self._key)).decode("utf-8")
        if len(envelope)>MAX_ENVELOPE:
            raise ValueError("checkpoint size limit")
        db.execute("INSERT INTO history VALUES(?,?)",(state["revision"],envelope))
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
                "production_qualified":False,
                "external_anchor_revision":self._anchor["bindings"]["revision"] if self._anchor is not None else 0,
                "external_anchor_verified":self._anchor is not None}

    def report(self):
        """Host-only report. No keys, raw payloads or sensor/operator names."""
        with self._transaction() as db:
            state=self._load(db)
            return self._report(state,self._now(state))

    def history(self):
        """Verified, bounded historical incident transitions, not raw logs."""
        with self._transaction() as db:
            state=self._load(db)
            states=self._verified_history(db)
            result=[]
            for old,new in zip(states,states[1:]):
                if new["sequence"]==old["sequence"]+1:
                    kinds=[k for k in KINDS if new["counts"].get(k,0)>old["counts"].get(k,0)]
                    if len(kinds)!=1:
                        raise ValueError("history event transition mismatch")
                    item={"type":"event","kind":kinds[0],"sequence":new["sequence"],
                          "alerts":{k:v-old["pending"].get(k,0) for k,v in new["pending"].items()
                                    if v>old["pending"].get(k,0)}}
                elif new["reviews"]==old["reviews"]+1:
                    item={"type":"operator_review","acknowledged":dict(old["pending"])}
                else:
                    raise ValueError("history revision transition mismatch")
                result.append({**item,"revision":new["revision"],"received_at_utc":new["last_seen"],
                               "state_sha256":digest(new)})
            return {"schema":"wilborn-security-history/1","environment":"demo","data_class":"synthetic",
                    "revision":state["revision"],"entries":result,"execution_authorized":False}

    def observe_local(self,event,signer):
        """Host-only sensor callback. Allocate and sign the next sequence under one lock."""
        if type(event) is not SecurityEvent or not callable(signer):
            raise TypeError("trusted typed event and local signer required")
        event.__post_init__()
        with self._transaction() as db:
            state=self._load(db)
            now=self._now(state)
            binding=event_bindings(self._id,state["sequence"]+1,event.kind)
            # Trusted, local, bounded signer: must not reenter the ledger or do network I/O.
            attestation=signer(deepcopy(binding),now)
            return self._ingest_verified(db,state,now,binding,attestation)

    def ingest(self,bindings,attestation):
        if type(bindings) is not dict:
            raise TypeError("typed signed event required")
        expected=event_bindings(self._id,bindings.get("sequence"),bindings.get("kind"))
        if canonical(bindings)!=canonical(expected):
            raise PermissionError("event schema or ledger mismatch")
        with self._transaction() as db:
            state=self._load(db)
            now=self._now(state)
            return self._ingest_verified(db,state,now,expected,attestation)

    def _ingest_verified(self,db,state,now,expected,attestation):
        event_digest=digest(expected)
        fresh_attestation(attestation,trust=self._sensor,claim_id=EVENT_CLAIM,
            bundle_sha256=event_digest,bindings=expected,requester_id=self._requester,
            purpose="artifact-integrity",now=datetime.fromtimestamp(now,timezone.utc),max_age_seconds=600)
        sequence=expected["sequence"]
        if sequence==state["sequence"] and state["last_event"]==event_digest:
            return {**self._report(state,now),"duplicate":True}
        if sequence!=state["sequence"]+1:
            raise PermissionError("event sequence gap, conflict or replay")
        if state["revision"]>=MAX_HISTORY:
            raise OverflowError("incident history capacity reached; reviewed archival required")
        previous=digest(state)
        kind=expected["kind"]
        windows=self._windows(state)
        triggered,_=advance_windows(windows,kind,now)
        state["counts"][kind]=state["counts"].get(kind,0)+1
        for alert in sorted(set(triggered)|({kind} if kind in REVIEW_KINDS else set())):
            state["pending"][alert]=state["pending"].get(alert,0)+1
        state["sequence"]=sequence
        state["last_event"]=event_digest
        state["revision"]+=1
        state["previous_sha256"]=previous
        self._keep_windows(state,windows,now)
        self._save(db,state)
        return {**self._report(state,now),"duplicate":False,"kind":kind,
                "correlation_alerts":triggered,"requires_review":kind in REVIEW_KINDS or bool(triggered)}

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
            if state["revision"]>=MAX_HISTORY:
                raise OverflowError("incident history capacity reached; reviewed archival required")
            previous=digest(state)
            windows=self._windows(state)
            expire_windows(windows,now)
            state["pending"]={}
            state["reviews"]+=1
            state["last_review"]=verified["statement_sha256"]
            state["revision"]+=1
            state["previous_sha256"]=previous
            self._keep_windows(state,windows,now)
            self._save(db,state)
            return self._report(state,now)
