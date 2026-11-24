"""Durable, trusted-local synthetic writer handover across reviewed rotations.

The coordinator owns writer authority, not incident data. All enrolled writes
hold its SQLite lock through the ledger commit. No time-based lease, network
service, production activation, distributed consensus or independent custody.
The host must protect the original files from replacement/rollback and use a
local filesystem with working SQLite locks and sync. Pre-enrollment copies
and a malicious owner with keys/raw SQL remain outside this boundary.
"""
from contextlib import contextmanager,closing,ExitStack,nullcontext
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sqlite3

from python.merlin.artifact_ref import ArtifactRef
from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .security_archive import inspect_archive,_issued,_read_json
from .security_ledger import SecurityLedger,_uuid,_integer
from .security_recovery import AnchorCustody,private_database,private_directory,sync_directory
from .security_rotation import inspect_rotation,_roles
from .titan_envelope import seal_demo,open_demo

CLAIM="wilborn:security:local-writer-handover:v1"
MAX_CONTROL=65536
ENROLLMENT_VERSION=1
MAX_HANDOVERS=7


@dataclass(frozen=True)
class WriterLease:
    """Host-local fencing token; not authentication of a person or a service."""
    handover_id:str
    epoch:int
    owner_id:str

    def __post_init__(self):
        _uuid(self.handover_id)
        _integer(self.epoch,1)
        _uuid(self.owner_id)


def _ref(identity,kind,sha):
    return ArtifactRef("wilborn-demo","security/wilborn/synthetic_fixture/"+
                       identity+"/"+kind,1,sha).to_dict()


def _seal(value,identity,kind,key_id,key):
    return canonical(seal_demo(canonical(value),artifact_ref=_ref(identity,kind,digest(value)),
                               key_id=key_id,master_key=key))


def _open(raw,identity,kind,key_id,key):
    if type(raw) is not bytes or not 1<=len(raw)<=MAX_CONTROL:
        raise ValueError("bounded canonical writer record required")
    envelope=json.loads(raw)
    if canonical(envelope)!=raw:
        raise ValueError("noncanonical writer envelope")
    sha=envelope["context"]["artifact_ref"]["sha256"]
    plain=open_demo(envelope,artifact_ref=_ref(identity,kind,sha),key_id=key_id,master_key=key)
    value=json.loads(plain)
    if canonical(value)!=plain:
        raise ValueError("noncanonical writer record")
    return value


def read_enrollment(ledger,db):
    """Read each time, including on objects opened before enrollment."""
    version=db.execute("PRAGMA user_version").fetchone()[0]
    exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='writer_enrollment'").fetchone()
    if version==0 and exists is None:
        return None
    if version!=ENROLLMENT_VERSION or exists is None:
        raise PermissionError("writer enrollment metadata missing or unsupported")
    rows=db.execute("SELECT slot,length(envelope) FROM writer_enrollment").fetchall()
    if len(rows)!=1 or rows[0][0]!=1 or not 1<=rows[0][1]<=MAX_CONTROL:
        raise PermissionError("writer enrollment metadata invalid")
    raw=db.execute("SELECT envelope FROM writer_enrollment WHERE slot=1").fetchone()[0]
    value=_open(raw,ledger._id,"writer-enrollment",ledger._key_id,ledger._key)
    fields={"schema","handover_id","coordinator","config_sha256","ledger_id","ledger_path","role"}
    if (type(value) is not dict or set(value)!=fields or
            value["schema"]!="wilborn-writer-enrollment/1" or
            value["ledger_id"]!=ledger._id or value["ledger_path"]!=str(ledger._path) or
            value["role"] not in ("predecessor","successor")):
        raise PermissionError("writer enrollment identity or path differs")
    _uuid(value["handover_id"])
    return value


@contextmanager
def _control_transaction(path):
    path=private_database(path)
    with closing(sqlite3.connect(path.as_uri()+"?mode=rw",uri=True,timeout=5)) as db:
        db.execute("PRAGMA trusted_schema=OFF")
        if db.execute("PRAGMA journal_mode").fetchone()[0]!="delete":
            raise PermissionError("local rollback journal required for writer control")
        db.execute("PRAGMA synchronous=EXTRA")
        db.execute("BEGIN IMMEDIATE")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise


def _read_control(db,identity,config,key_id,key):
    rows=db.execute("SELECT slot,length(envelope) FROM writer_control").fetchall()
    if len(rows)!=1 or rows[0][0]!=1 or not 1<=rows[0][1]<=MAX_CONTROL:
        raise PermissionError("writer control missing or invalid")
    raw=db.execute("SELECT envelope FROM writer_control WHERE slot=1").fetchone()[0]
    state=_open(raw,identity,"writer-control",key_id,key)
    fields={"schema","handover_id","config_sha256","plan","phase","epoch","owner_id","attestation"}
    if type(state) is dict and state.get("phase")=="retired":
        fields.add("retirement")
    if (type(state) is not dict or set(state)!=fields or
            state["schema"]!="wilborn-writer-control/1" or
            state["handover_id"]!=identity or state["config_sha256"]!=config or
            state["phase"] not in ("preparing","ready","active","retired")):
        raise PermissionError("writer control identity or state differs")
    _uuid(state["owner_id"])
    _integer(state["epoch"])
    if state["phase"] in ("active","retired"):
        if state["epoch"]<1 or type(state["attestation"]) is not dict:
            raise PermissionError("active writer grant missing")
    elif state["epoch"]!=0 or state["attestation"] is not None:
        raise PermissionError("inactive writer authority")
    return state


@contextmanager
def writer_guard(ledger,enrollment,lease):
    if enrollment["role"]!="successor" or type(lease) is not WriterLease:
        raise PermissionError("ledger fenced; current successor writer lease required")
    private_database(ledger._path)
    with _control_transaction(Path(enrollment["coordinator"])) as db:
        state=_read_control(db,enrollment["handover_id"],enrollment["config_sha256"],
                            ledger._key_id,ledger._key)
        if (state["phase"]!="active" or lease!=WriterLease(state["handover_id"],
                state["epoch"],state["owner_id"]) or
                state["plan"]["successor_ledger_id"]!=ledger._id):
            raise PermissionError("stale or inactive writer lease")
        custody=getattr(ledger,"_writer_custody",None)
        expected=state["plan"].get("successor_custody")
        if (type(custody) is not AnchorCustody or expected is None or
                expected!={"directory":str(custody._directory),"config_sha256":custody._config} or
                custody._id!=ledger._id or custody._trust!=ledger._anchor_keys or
                custody._requester!=ledger._requester):
            raise PermissionError("custody-bound handover and configured current custody required")
        # Keep the current retained receipt stable through the ledger commit.
        # Lock order is coordinator -> custody -> ledger; retain uses custody only.
        with custody._transaction() as custody_db:
            anchor=custody._read(custody_db)
            custody._verify(anchor,fresh=True)
            ledger._anchor=deepcopy(anchor)
            yield


class WriterHandover:
    """Host-administered, bounded lineage; its methods are not public endpoints.

    PREPARING -> READY -> ACTIVE. Enrollment is permanent and freezes both
    APIs; activation opens only the successor. Restart uses a compare-and-swap
    epoch claim which fences all previous tokens. A subsequent transfer retires
    this coordinator permanently and preserves its original enrollment/grant.
    No automatic takeover. At most seven transfers/eight segments per lineage.
    """
    def __init__(self,directory,*,handover_id,source,archive,stage,predecessor,successor,
                 old_options,new_options,archive_review_keys,reserve_revisions,
                 rotation_review_keys,handover_review_keys,create=False,owner_id=None,previous=None):
        _roles(predecessor,successor,old_options,new_options,archive_review_keys,rotation_review_keys)
        for trust in (predecessor._trust,successor._trust,old_options["sensor_keys"],
                old_options["operator_keys"],new_options["sensor_keys"],new_options["operator_keys"],
                archive_review_keys,rotation_review_keys):
            separated_trust(trust,handover_review_keys)
        if type(create) is not bool:
            raise ValueError("explicit creation flag required")
        self._directory=private_directory(directory)
        self._path=self._directory/"writer-control.sqlite3"
        self._id=_uuid(handover_id)
        self._source=private_database(source)
        self._archive=private_directory(archive)
        self._stage=private_directory(stage)
        self._target=private_database(self._stage/"successor.sqlite3")
        if self._directory in (self._source.parent,self._archive,self._stage,
                               predecessor._directory,successor._directory):
            raise PermissionError("writer control requires separate private directory")
        self._old=predecessor
        self._new=successor
        self._old_options=deepcopy(old_options)
        self._new_options=deepcopy(new_options)
        self._trust=deepcopy(handover_review_keys)
        if previous is not None and type(previous) is not WriterHandover:
            raise TypeError("previous handover must be host configured")
        self._previous=previous
        if previous is not None and (self._source!=previous._target or
                self._old._id!=previous._new._id or self._old._config!=previous._new._config or
                self._old._directory!=previous._new._directory or
                self._old_options!=previous._new_options):
            raise PermissionError("continuation must use the exact previous successor and custody")
        self._rotation=dict(predecessor=predecessor,successor=successor,
            old_options=self._old_options,new_options=self._new_options,
            archive_review_keys=deepcopy(archive_review_keys),reserve_revisions=reserve_revisions,
            rotation_review_keys=deepcopy(rotation_review_keys))
        config={"handover_id":self._id,"control":str(self._path),
            "source":str(self._source),"archive":str(self._archive),"stage":str(self._stage),
            "old_custody":predecessor._config,"new_custody":successor._config,
            "old_keys":{k:v for k,v in old_options.items() if k!="master_key"},
            "new_keys":{k:v for k,v in new_options.items() if k!="master_key"},
            "archive_trust":archive_review_keys,"rotation_trust":rotation_review_keys,
            "handover_trust":handover_review_keys,"reserve":reserve_revisions}
        if previous is not None:
            config["previous"]=previous._descriptor()
        self._config=digest(config)
        self._lineage()  # Reject cycles, reused paths/IDs and policy overflow before writes.
        if create:
            owner_id=_uuid(owner_id)
            context=previous._lineage_transactions() if previous else nullcontext([])
            with context as parents:
                if previous:
                    previous._verify_lineage(parents)
                    if parents[-1][2]["phase"]!="active":
                        raise PermissionError("only current active owner can start a continuation")
                proof=self._rotation_proof()
                reviewed=self._inspect_rotation()
                if proof!=self._rotation_proof():
                    raise PermissionError("rotation proof changed during handover creation")
                b=reviewed["review_bindings"]
                plan={**b,**proof,"rotation_statement_sha256":reviewed["review_statement_sha256"],
                    "predecessor_unresolved_alerts":reviewed["predecessor_unresolved_alerts"],
                    "initial_owner_id":owner_id,
                    "predecessor_custody":self._custody_descriptor(self._old),
                    "successor_custody":self._custody_descriptor(self._new)}
                if previous:
                    plan["previous"]=previous._parent_binding(parents[-1][2])
            state={"schema":"wilborn-writer-control/1","handover_id":self._id,
                "config_sha256":self._config,"plan":plan,"phase":"preparing",
                "epoch":0,"owner_id":owner_id,"attestation":None}
            fd=os.open(self._path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            os.close(fd)
            with closing(sqlite3.connect(self._path)) as db,db:
                db.execute("PRAGMA synchronous=EXTRA")
                db.execute("CREATE TABLE writer_control (slot INTEGER PRIMARY KEY CHECK(slot=1), envelope BLOB NOT NULL)")
                db.execute("INSERT INTO writer_control VALUES(1,?)",(self._encode(state),))
            sync_directory(self._directory)
        elif owner_id is not None:
            raise ValueError("initial owner is set only on explicit creation")
        with _control_transaction(self._path) as db:
            self._read(db)

    def _encode(self,state):
        return _seal(state,self._id,"writer-control",self._new_options["key_id"],self._new_options["master_key"])

    def _read(self,db):
        state=_read_control(db,self._id,self._config,self._new_options["key_id"],self._new_options["master_key"])
        for name,custody in (("predecessor",self._old),("successor",self._new)):
            if name+"_custody" in state["plan"] and state["plan"][name+"_custody"]!=self._custody_descriptor(custody):
                raise PermissionError("handover custody location differs")
        if ("previous" in state["plan"])!=(self._previous is not None):
            raise PermissionError("complete pinned handover ancestry required")
        return state

    @staticmethod
    def _custody_descriptor(custody):
        return {"directory":str(custody._directory),"config_sha256":custody._config}

    def _descriptor(self):
        return {"handover_id":self._id,"coordinator":str(self._path),"config_sha256":self._config}

    def _parent_binding(self,state):
        return {**self._descriptor(),"plan_sha256":digest(state["plan"]),
                "epoch":state["epoch"],"owner_id":state["owner_id"]}

    def _lineage(self):
        lineage=[]
        current=self
        while current is not None:
            if type(current) is not WriterHandover or len(lineage)>=MAX_HANDOVERS:
                raise PermissionError("bounded complete handover ancestry required")
            if any(current._id==item._id or current._path==item._path for item in lineage):
                raise PermissionError("handover cycle or repeated identity")
            lineage.append(current)
            current=current._previous
        lineage=list(reversed(lineage))
        protected={directory for item in lineage for directory in
                   (item._archive,item._stage,item._old._directory,item._new._directory,item._source.parent)}
        if any(item._directory in protected for item in lineage):
            raise PermissionError("writer controls must remain outside every lineage evidence directory")
        segments=[(lineage[0]._old._id,lineage[0]._source,lineage[0]._old_options)]
        segments.extend((item._new._id,item._target,item._new_options) for item in lineage)
        for values in ([item[0] for item in segments],[item[1] for item in segments],
                       [item[2]["key_id"] for item in segments],[item[2]["master_key"] for item in segments]):
            if len(set(values))!=len(values):
                raise PermissionError("lineage requires distinct segment identities, paths and encryption keys")
        return lineage

    @contextmanager
    def _lineage_transactions(self):
        # Every multi-control operation locks ancestors before descendants.
        with ExitStack() as stack:
            records=[]
            for control in self._lineage():
                db=stack.enter_context(_control_transaction(control._path))
                records.append((control,db,control._read(db)))
            yield records

    def _retirement(self,state):
        plan=state["plan"]
        return {"schema":"wilborn-writer-retirement/1","next":self._descriptor(),
                "next_plan_sha256":digest(plan),"previous":plan["previous"],
                "ledger_id":self._old._id,"revision":plan["predecessor_revision"],
                "state_sha256":plan["predecessor_state_sha256"],
                "unresolved_alerts":plan["predecessor_unresolved_alerts"],
                "execution_authorized":False,"deployment_authorized":False}

    def _verify_ancestors(self,records):
        for (parent,_,parent_state),(child,_,child_state) in zip(records,records[1:]):
            if (parent_state["phase"]!="retired" or
                    child_state["plan"].get("previous")!=parent._parent_binding(parent_state) or
                    parent_state.get("retirement")!=child._retirement(child_state)):
                raise PermissionError("missing, branched or mismatched durable retirement")
            parent._resume_check(parent_state)

    def _verify_lineage(self,records):
        self._verify_ancestors(records)
        state=records[-1][2]
        if state["phase"] not in ("active","retired"):
            raise PermissionError("reviewed active or retired handover required")
        return self._resume_check(state)

    def _save(self,db,state):
        encoded=self._encode(state)
        if len(encoded)>MAX_CONTROL:
            raise ValueError("writer control size bound")
        db.execute("UPDATE writer_control SET envelope=? WHERE slot=1",(encoded,))

    def _inspect_rotation(self):
        return inspect_rotation(self._source,self._archive,self._stage,**self._rotation)

    def _rotation_proof(self):
        return {"continuity_file_sha256":digest(_read_json(self._stage/"continuity.json")),
                "rotation_review_file_sha256":digest(_read_json(self._stage/"review.json"))}

    def _ledger(self,role):
        custody,path,options=(self._old,self._source,self._old_options) if role=="predecessor" else (self._new,self._target,self._new_options)
        return custody.open_ledger(path,**options)

    def _enrollment(self,ledger,role):
        return {"schema":"wilborn-writer-enrollment/1","handover_id":self._id,
                "coordinator":str(self._path),"config_sha256":self._config,
                "ledger_id":ledger._id,"ledger_path":str(ledger._path),"role":role}

    def _freeze(self,role):
        ledger=self._ledger(role)
        expected=(self._previous._enrollment(ledger,"successor")
                  if role=="predecessor" and self._previous else self._enrollment(ledger,role))
        with ledger._transaction() as db:
            existing=read_enrollment(ledger,db)
            if role=="predecessor" and self._previous:
                if existing!=expected:
                    raise PermissionError("previous successor enrollment must remain intact")
                return
            if existing is not None:
                if existing!=expected:
                    raise PermissionError("ledger already enrolled in another handover")
                return
            ledger._load(db)
            raw=_seal(expected,ledger._id,"writer-enrollment",ledger._key_id,ledger._key)
            db.execute("CREATE TABLE writer_enrollment (slot INTEGER PRIMARY KEY CHECK(slot=1), envelope BLOB NOT NULL)")
            db.execute("INSERT INTO writer_enrollment VALUES(1,?)",(raw,))
            db.execute("PRAGMA user_version=1")
        sync_directory(ledger._path.parent)

    def _check_enrolled(self):
        for role in ("successor","predecessor"):
            ledger=self._ledger(role)
            with ledger._transaction() as db:
                expected=(self._previous._enrollment(ledger,"successor")
                    if role=="predecessor" and self._previous else self._enrollment(ledger,role))
                if read_enrollment(ledger,db)!=expected:
                    raise PermissionError("both exact ledger enrollments required")

    def _validate_rotation(self,state):
        reviewed=self._inspect_rotation()
        plan=state["plan"]
        if (reviewed["review_statement_sha256"]!=plan["rotation_statement_sha256"] or
                reviewed["predecessor_unresolved_alerts"]!=plan["predecessor_unresolved_alerts"] or
                any(reviewed["review_bindings"][k]!=plan[k] for k in reviewed["review_bindings"]) or
                any(plan[k]!=v for k,v in self._rotation_proof().items())):
            raise PermissionError("reviewed rotation changed; successor remains fenced")

    def _retire_parent(self,records):
        parent,parent_db,parent_state=records[-2]
        state=records[-1][2]
        expected=self._retirement(state)
        if parent_state["phase"]=="retired":
            if parent_state["retirement"]!=expected:
                raise PermissionError("previous owner already retired to another handover")
            self._verify_ancestors(records)
            return
        self._verify_ancestors(records[:-1])
        if (parent_state["phase"]!="active" or
                state["plan"]["previous"]!=parent._parent_binding(parent_state)):
            raise PermissionError("previous ownership changed after continuation was staged")
        parent._resume_check(parent_state)
        self._freeze("predecessor")
        self._validate_rotation(state)
        parent_state.update(phase="retired",retirement=expected)
        parent._save(parent_db,parent_state)

    def _binding(self,state):
        return {"schema":"wilborn-local-writer-handover/1","environment":"demo",
            "data_class":"synthetic","handover_id":self._id,"config_sha256":self._config,
            "plan_sha256":digest(state["plan"]),"successor_ledger_id":self._new._id,
            "epoch":1,"owner_id":state["plan"]["initial_owner_id"],
            "decision":"enable_local_synthetic_successor_writes",
            "production_qualified":False,"execution_authorized":False,"deployment_authorized":False}

    def prepare(self):
        """Persist intent first, then freeze successor before predecessor.

        A crash between steps can stop progress but cannot open a writer.
        Retry resumes the same intent; changed tips stay fenced for review.
        """
        with self._lineage_transactions() as records:
            _,db,state=records[-1]
            if state["phase"] not in ("preparing","ready"):
                raise PermissionError("active or retired handover cannot be prepared again")
            self._freeze("successor")
            if self._previous:
                self._retire_parent(records)
            else:
                self._freeze("predecessor")
        # All locks are released only after parent retirement is durably
        # committed. A crash here leaves the child preparing, never writable.
        with self._lineage_transactions() as records:
            _,db,state=records[-1]
            if state["phase"] not in ("preparing","ready"):
                raise PermissionError("handover state changed during preparation")
            self._verify_ancestors(records)
            self._check_enrolled()
            self._validate_rotation(state)
            state["phase"]="ready"
            self._save(db,state)
            return self._binding(state)

    def _verify_grant(self,state,attestation,*,fresh):
        now=datetime.fromtimestamp(self._new._clock(),timezone.utc)
        issued=_issued(attestation)
        if issued>now:
            raise PermissionError("handover review issued in future")
        if fresh and issued<_issued(_read_json(self._stage/"review.json")):
            raise PermissionError("handover review must follow rotation review")
        binding=self._binding(state)
        fresh_attestation(attestation,trust=self._trust,claim_id=CLAIM,
            bundle_sha256=digest(binding),bindings=binding,requester_id=self._new._requester,
            purpose="independent-reproduction",now=now if fresh else issued,max_age_seconds=86400)

    def activate(self,attestation):
        """A separate signed grant enables synthetic writes; never deployment."""
        attestation=deepcopy(attestation)
        with self._lineage_transactions() as records:
            _,db,state=records[-1]
            self._verify_ancestors(records)
            if state["phase"]=="active":
                if state["attestation"]!=attestation:
                    raise PermissionError("different grant cannot replay handover")
                self._verify_grant(state,attestation,fresh=False)
                self._resume_check(state)
                # A retry cannot hand an old owner a newer owner's token.
                return WriterLease(self._id,1,state["plan"]["initial_owner_id"])
            if state["phase"]!="ready":
                raise PermissionError("prepared handover required")
            self._check_enrolled()
            self._validate_rotation(state)
            self._verify_grant(state,attestation,fresh=True)
            state.update(phase="active",epoch=1,attestation=attestation)
            self._save(db,state)
            return WriterLease(self._id,1,state["owner_id"])

    def _resume_check(self,state):
        self._check_enrolled()
        self._verify_grant(state,state["attestation"],fresh=False)
        old=self._ledger("predecessor").report()
        plan=state["plan"]
        if any(plan[k]!=v for k,v in self._rotation_proof().items()):
            raise PermissionError("retained rotation proof changed")
        if (old["revision"]!=plan["predecessor_revision"] or
                old["state_sha256"]!=plan["predecessor_state_sha256"] or
                old["pending_alerts"]!=plan["predecessor_unresolved_alerts"]):
            raise PermissionError("frozen predecessor differs")
        reviewed=inspect_archive(self._archive,custody=self._old,options=self._old_options,
                                 reviewer_keys=self._rotation["archive_review_keys"])
        b=reviewed["archive_binding"]
        if b["revision"]!=old["revision"] or b["state_sha256"]!=old["state_sha256"]:
            raise PermissionError("retained predecessor archive differs")
        ledger=self._ledger("successor")
        with ledger._transaction() as db:
            state_now,states=ledger._load_verified(db)
            if digest(states[0])!=plan["successor_genesis_sha256"]:
                raise PermissionError("successor no longer extends reviewed genesis")
            ledger._history_report(state_now,states)
            if state["phase"]=="retired":
                retirement=state["retirement"]
                if (retirement["ledger_id"]!=ledger._id or
                        retirement["revision"]!=state_now["revision"] or
                        retirement["state_sha256"]!=digest(state_now) or
                        retirement["unresolved_alerts"]!=state_now["pending"]):
                    raise PermissionError("retired successor differs from frozen checkpoint")
        return ledger

    def claim_writer(self,*,expected_epoch,owner_id):
        """Explicit trusted-host restart/takeover; CAS fences every old token."""
        _integer(expected_epoch,1)
        _uuid(owner_id)
        with self._lineage_transactions() as records:
            _,db,state=records[-1]
            if state["phase"]!="active" or state["epoch"]!=expected_epoch:
                raise PermissionError("writer epoch changed or handover inactive")
            if owner_id==state["owner_id"]:
                raise ValueError("restart requires a new owner identity")
            self._verify_lineage(records)
            state.update(epoch=_integer(expected_epoch+1,1),owner_id=owner_id)
            self._save(db,state)
            return WriterLease(self._id,state["epoch"],owner_id)

    def open_writer(self,lease):
        with self._lineage_transactions() as records:
            _,db,state=records[-1]
            if (state["phase"]!="active" or type(lease) is not WriterLease or
                    lease!=WriterLease(self._id,state["epoch"],state["owner_id"])):
                raise PermissionError("current writer lease required")
            ledger=self._verify_lineage(records)
            if state["plan"].get("successor_custody")!=self._custody_descriptor(self._new):
                raise PermissionError("legacy handover needs a reviewed custody-bound grant")
            ledger._writer_lease=lease
            ledger._writer_custody=self._new
            return ledger

    def status(self):
        with self._lineage_transactions() as records:
            _,db,state=records[-1]
            if state["phase"] in ("active","retired"):
                self._verify_lineage(records)
            return {"schema":"wilborn-local-writer-handover-status/1","environment":"demo",
                "data_class":"synthetic","handover_id":self._id,"phase":state["phase"],
                "epoch":state["epoch"],"local_writer_handover_verified":state["phase"]=="active",
                "predecessor_unresolved_alerts":deepcopy(state["plan"]["predecessor_unresolved_alerts"]),
                "predecessor_alerts_resolved":False,"production_qualified":False,
                "execution_authorized":False,"deployment_authorized":False}

    def lineage_snapshot(self):
        """Complete coherent incident snapshots under all ownership locks.

        The caller supplies the complete pinned ancestry, never a truncated
        selection of reports. Current custody and all retained proofs are
        checked. This is a host verification result, not public authentication.
        """
        with self._lineage_transactions() as records:
            state=records[-1][2]
            if state["phase"]!="active":
                raise PermissionError("latest active handover required for lineage review")
            self._verify_lineage(records)
            segments=[records[0][0]._ledger("predecessor").review_snapshot()]
            segments.extend(control._ledger("successor").review_snapshot() for control,_,_ in records)
            ids=[report["ledger_id"] for report,_ in segments]
            if len(ids)!=len(set(ids)):
                raise PermissionError("repeated ledger in handover lineage")
            for index,(_,_,edge) in enumerate(records):
                before,after=segments[index][0],segments[index+1][0]
                plan=edge["plan"]
                if (before["ledger_id"]!=plan["predecessor_ledger_id"] or
                        after["ledger_id"]!=plan["successor_ledger_id"] or
                        before["revision"]!=plan["predecessor_revision"] or
                        before["state_sha256"]!=plan["predecessor_state_sha256"] or
                        before["pending_alerts"]!=plan["predecessor_unresolved_alerts"]):
                    raise PermissionError("lineage snapshot differs from reviewed boundary")
            return {"ownership_epoch":state["epoch"],"segments":segments}
