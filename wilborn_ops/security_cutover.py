"""Offline synthetic-only staged ledger cutover.

The old encrypted database and aggregate evidence are preserved verbatim.
A new ledger starts at genesis, with new identity and key. A sealed link and
separate signed review establish provenance, not activation or authorization.
No key generation, service startup, production data or external calls.
"""
import hashlib
import json
import os
from datetime import datetime,timezone
from pathlib import Path

from python.merlin.artifact_ref import ArtifactRef
from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .security_ledger import SecurityLedger
from .security_recovery import AnchorCustody,private_database,private_directory,sync_directory,inspect_legacy_checkpoint
from .titan_envelope import seal_demo,open_demo

CLAIM="wilborn:security:staged-cutover-review:v1"
OPTIONS={"master_key","key_id","sensor_keys","operator_keys"}
LINK_LIMIT=32768

def _validate(legacy,successor,old,new):
    if type(legacy) is not AnchorCustody or type(successor) is not AnchorCustody:
        raise TypeError("two separately configured custody stores required")
    if legacy._id==successor._id or legacy._directory==successor._directory:
        raise PermissionError("distinct predecessor and successor identities required")
    for options in (old,new):
        if type(options) is not dict or set(options)!=OPTIONS:
            raise ValueError("exact host ledger configuration required")
        if type(options["master_key"]) is not bytes or len(options["master_key"])!=32:
            raise ValueError("host-managed 256-bit key required")
    if old["master_key"]==new["master_key"] or old["key_id"]==new["key_id"]:
        raise PermissionError("successor must use a new key and key identity")
    for options,custody in ((old,legacy),(new,successor)):
        separated_trust(options["sensor_keys"],options["operator_keys"])
        separated_trust(options["sensor_keys"],custody._trust)
        separated_trust(options["operator_keys"],custody._trust)

def _quiet(path):
    path=private_database(path)
    for suffix in ("-wal","-shm","-journal"):
        side=Path(str(path)+suffix)
        if side.exists() or side.is_symlink():
            raise PermissionError("offline quiesced database required")
    return path

def _hash(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(65536),b""):
            h.update(chunk)
    return h.hexdigest()

def _write(path,content):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())

def _archive(source,target):
    # Copy encrypted bytes only; no plaintext or key material written.
    source=_quiet(source)
    before=_hash(source)
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with source.open("rb") as inp,os.fdopen(fd,"wb") as out:
        for chunk in iter(lambda:inp.read(65536),b""):
            out.write(chunk)
        out.flush()
        os.fsync(out.fileno())
    if _hash(_quiet(source))!=before or _hash(private_database(target))!=before:
        raise PermissionError("legacy source changed during archive")
    return before

def _genesis(report):
    if (report["revision"]!=1 or report["accepted_events"]!=0
            or report["operator_reviews"]!=0 or report["counts"]
            or report["pending_alerts"] or report["active_correlations"]):
        raise PermissionError("successor must remain at untouched genesis")
    return report["state_sha256"]

def _link(legacy,successor,summary,archive_sha,genesis_sha):
    return {"schema":"wilborn-legacy-cutover-link/1","environment":"demo",
            "data_class":"synthetic","legacy_ledger_id":legacy._id,
            "successor_ledger_id":successor._id,
            "legacy_archive_sha256":archive_sha,"legacy_summary":summary,
            "successor_genesis_sha256":genesis_sha,
            "historical_incidents_reconstructed":0,
            "activation_authorized":False,"execution_authorized":False}

def _ref(successor,sha):
    return ArtifactRef("wilborn-demo","security/wilborn/synthetic_fixture/"+successor._id+"/cutover-link",
                       1,sha).to_dict()

def _review_binding(link):
    return {"schema":"wilborn-staged-cutover-review/1","environment":"demo",
            "data_class":"synthetic","legacy_ledger_id":link["legacy_ledger_id"],
            "legacy_archive_sha256":link["legacy_archive_sha256"],
            "legacy_state_sha256":link["legacy_summary"]["state_sha256"],
            "successor_ledger_id":link["successor_ledger_id"],
            "successor_genesis_sha256":link["successor_genesis_sha256"],
            "link_sha256":digest(link),"decision":"review_staged_cutover",
            "activation_authorized":False,"execution_authorized":False}

def stage_cutover(source,directory,*,legacy,successor,old_options,new_options):
    """Stage an archived predecessor, untouched successor and sealed link.

    Destination must be new. On failure retain partial files for operator
    review; no complete link means no reviewable candidate. Never auto-activate.
    The trusted host must quiesce all writers and prevent concurrent use.
    """
    _validate(legacy,successor,old_options,new_options)
    source=_quiet(source)
    directory=Path(directory)
    parent=private_directory(directory.parent)
    if directory.resolve()!=directory or directory.exists() or directory.is_symlink():
        raise FileExistsError("new canonical staging directory required")
    if parent in (legacy._directory,successor._directory) or directory==source.parent:
        raise PermissionError("stage outside custody and source directories")
    with successor._transaction() as db:
        if successor._read(db,allow_empty=True) is not None:
            raise PermissionError("successor custody must be new and empty")
    summary=inspect_legacy_checkpoint(source,custody=legacy,**old_options)
    directory.mkdir(mode=0o700)
    archive=directory/"legacy.sqlite3"
    archive_sha=_archive(source,archive)
    if inspect_legacy_checkpoint(archive,custody=legacy,**old_options)!=summary:
        raise PermissionError("archived legacy evidence differs")
    ledger=SecurityLedger(directory/"successor.sqlite3",ledger_id=successor._id,
             requester_id=successor._requester,clock=successor._clock,create=True,**new_options)
    genesis_sha=_genesis(ledger.report())
    if inspect_legacy_checkpoint(source,custody=legacy,**old_options)!=summary or _hash(_quiet(source))!=archive_sha:
        raise PermissionError("legacy source changed during staging")
    link=_link(legacy,successor,summary,archive_sha,genesis_sha)
    sealed=seal_demo(canonical(link),artifact_ref=_ref(successor,digest(link)),
                     key_id=new_options["key_id"],master_key=new_options["master_key"])
    _write(directory/"link.json",canonical(sealed))
    sync_directory(directory)
    sync_directory(parent)
    return {"schema":"wilborn-staged-cutover/1","review_bindings":_review_binding(link),
            "successor_anchor_required":True,"review_required":True,
            "activation_authorized":False,"production_qualified":False}

def verify_staged_cutover(directory,*,legacy,successor,old_options,new_options,
                          reviewer_keys,review_attestation):
    """Verify exact staged package with two current anchors and separate review."""
    _validate(legacy,successor,old_options,new_options)
    for trust in (legacy._trust,successor._trust,old_options["sensor_keys"],
                  old_options["operator_keys"],new_options["sensor_keys"],new_options["operator_keys"]):
        separated_trust(trust,reviewer_keys)
    directory=private_directory(directory)
    if {p.name for p in directory.iterdir()}!={"legacy.sqlite3","successor.sqlite3","link.json"}:
        raise ValueError("exact completed stage inventory required")
    archive=_quiet(directory/"legacy.sqlite3")
    candidate=_quiet(directory/"successor.sqlite3")
    summary=inspect_legacy_checkpoint(archive,custody=legacy,**old_options)
    report=successor.open_ledger(candidate,**new_options).report()
    genesis_sha=_genesis(report)
    if report["external_anchor_revision"]!=1 or not report["external_anchor_verified"]:
        raise PermissionError("successor genesis must be anchored")
    link_path=private_database(directory/"link.json")
    if link_path.stat().st_size>LINK_LIMIT:
        raise ValueError("sealed link exceeds bound")
    raw=link_path.read_bytes()
    sealed=json.loads(raw)
    if canonical(sealed)!=raw:
        raise ValueError("noncanonical sealed link")
    expected=_link(legacy,successor,summary,_hash(archive),genesis_sha)
    plain=open_demo(sealed,artifact_ref=_ref(successor,digest(expected)),
                    key_id=new_options["key_id"],master_key=new_options["master_key"])
    if plain!=canonical(expected):
        raise PermissionError("staged provenance link mismatch")
    binding=_review_binding(expected)
    verified=fresh_attestation(review_attestation,trust=reviewer_keys,claim_id=CLAIM,
        bundle_sha256=digest(binding),bindings=binding,requester_id=successor._requester,
        purpose="independent-reproduction",
        now=datetime.fromtimestamp(successor._clock(),timezone.utc),max_age_seconds=86400)
    return {"schema":"wilborn-reviewed-staged-cutover/1","data_class":"synthetic",
            "review_bindings":binding,"review_statement_sha256":verified["statement_sha256"],
            "legacy_archive_verified":True,"successor_genesis_verified":True,
            "historical_incidents_reconstructed":0,"activation_authorized":False,
            "execution_authorized":False,"production_qualified":False}
