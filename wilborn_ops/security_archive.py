"""Reviewed encrypted archives, synthetic local host only.

Archive receipts are historical evidence, not fresh authorization. Never
returns a live ledger, deletes an event, resets a sequence, or activates a copy.
Host must quiesce writers and administer custody independently.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import tempfile

from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .security_ledger import SecurityLedger,MAX_HISTORY
from .security_recovery import (
    AnchorCustody,MAX_RECEIPT,private_database,private_directory,
    sync_directory,verified_recovery_copy)
from .security_cutover import _archive,_hash,_quiet,_write

ARCHIVE_CLAIM="wilborn:security:archive-review:v1"
STAGE_FILES={"history.sqlite3","anchor.json"}
OPTIONS={"master_key","key_id","sensor_keys","operator_keys"}

def retention_status(ledger,*,reserve_revisions):
    """Advisory only. Reserve is an explicit host policy, not an inferred SLA."""
    if type(ledger) is not SecurityLedger:
        raise TypeError("verified ledger required")
    if type(reserve_revisions) is not int or not 1<=reserve_revisions<MAX_HISTORY:
        raise ValueError("bounded explicit reserve required")
    report=ledger.report()
    remaining=MAX_HISTORY-report["revision"]
    return {"schema":"wilborn-retention-advisory/1","data_class":"synthetic",
            "revision":report["revision"],"revision_limit":MAX_HISTORY,
            "remaining_revisions":remaining,"reserve_revisions":reserve_revisions,
            "archive_review_due":remaining<=reserve_revisions,
            "capacity_exhausted":remaining==0,"deletion_authorized":False,
            "execution_authorized":False,"production_qualified":False}

def _read_json(path):
    path=private_database(path)
    if path.stat().st_size>MAX_RECEIPT:
        raise ValueError("archive receipt exceeds bound")
    raw=path.read_bytes()
    obj=json.loads(raw)
    if canonical(obj)!=raw:
        raise ValueError("archive receipt is not canonical")
    return obj

def _issued(attestation):
    return datetime.strptime(attestation["statement"]["created_at_utc"],
                             "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def _validate(custody,options,reviewer_keys=None):
    if type(custody) is not AnchorCustody or type(options) is not dict or set(options)!=OPTIONS:
        raise TypeError("host-configured custodian and ledger options required")
    separated_trust(options["sensor_keys"],options["operator_keys"])
    separated_trust(options["sensor_keys"],custody._trust)
    separated_trust(options["operator_keys"],custody._trust)
    if reviewer_keys is not None:
        for trust in (custody._trust,options["sensor_keys"],options["operator_keys"]):
            separated_trust(trust,reviewer_keys)

def _inventory(directory,reviewed):
    directory=private_directory(directory)
    expected=STAGE_FILES|({"review.json"} if reviewed else set())
    if {p.name for p in directory.iterdir()}!=expected:
        raise ValueError("exact archive inventory required")
    return directory

def _binding(receipt,archive_sha):
    b=receipt["bindings"]
    return {"schema":"wilborn-encrypted-history-archive/1","environment":"demo",
            "data_class":"synthetic","ledger_id":b["ledger_id"],"revision":b["revision"],
            "state_sha256":b["state_sha256"],"encrypted_database_sha256":archive_sha,
            "anchor_receipt_sha256":digest(receipt),"decision":"review_historical_archive",
            "deletion_authorized":False,"activation_authorized":False,"execution_authorized":False}

def _inspect(directory,*,custody,options,reviewed,fresh):
    directory=_inventory(directory,reviewed)
    source=_quiet(directory/"history.sqlite3")
    receipt=_read_json(directory/"anchor.json")
    custody._verify(receipt,fresh=fresh)
    b=receipt["bindings"]
    if fresh and custody.latest()["bindings"]!=b:
        raise PermissionError("staged archive no longer matches current retained tip")
    sha=_hash(source)
    # Review a temporary copy rather than opening the protected archive
    # read-write. Historical clock is only used inside this inspection;
    # a historical receipt must never be treated as a fresh recovery lease.
    historical_time=int(_issued(receipt["attestation"]).timestamp())
    with tempfile.TemporaryDirectory(prefix="wilborn-archive-inspect-") as folder:
        copy=Path(folder).resolve()/"inspection.sqlite3"
        if _archive(source,copy)!=sha:
            raise PermissionError("archive changed during inspection")
        ledger=SecurityLedger(copy,ledger_id=custody._id,requester_id=custody._requester,
                    clock=lambda:historical_time,anchor_keys=custody._trust,anchor=receipt,
                    min_revision=b["revision"],**options)
        report,history=ledger.review_snapshot()
        if (report["revision"]!=b["revision"] or report["state_sha256"]!=b["state_sha256"]
                or len(history["entries"])!=b["revision"]-1):
            raise PermissionError("archived checkpoint/history differs from signed anchor")
    if _hash(_quiet(source))!=sha:
        raise PermissionError("archive changed during inspection")
    return _binding(receipt,sha),receipt

def stage_archive(source,directory,*,custody,options):
    """Stage a verified encrypted backup and its current signed anchor."""
    _validate(custody,options)
    source=_quiet(source)
    directory=Path(directory)
    parent=private_directory(directory.parent)
    if directory.resolve()!=directory or directory.exists() or directory.is_symlink():
        raise FileExistsError("new private archival directory required")
    if parent==custody._directory or directory==source.parent:
        raise PermissionError("archive must be separate from source and custody")
    receipt=custody.latest()
    directory.mkdir(mode=0o700)
    result=verified_recovery_copy(source,directory/"history.sqlite3",custody=custody,**options)
    if (result["revision"]!=receipt["bindings"]["revision"] or
            result["state_sha256"]!=receipt["bindings"]["state_sha256"]):
        raise PermissionError("staged copy does not match retained receipt")
    _write(directory/"anchor.json",canonical(receipt))
    binding,_=_inspect(directory,custody=custody,options=options,reviewed=False,fresh=True)
    sync_directory(directory)
    sync_directory(parent)
    return {"schema":"wilborn-staged-archive/1","data_class":"synthetic",
            "review_bindings":binding,"review_required":True,
            "deletion_authorized":False,"activation_authorized":False,
            "execution_authorized":False,"production_qualified":False}

def _review(attestation,binding,receipt,*,custody,reviewer_keys,fresh):
    now=datetime.fromtimestamp(custody._clock(),timezone.utc)
    issued=_issued(attestation)
    if not _issued(receipt["attestation"])<=issued<=now:
        raise PermissionError("archive review time is outside valid history")
    return fresh_attestation(attestation,trust=reviewer_keys,claim_id=ARCHIVE_CLAIM,
        bundle_sha256=digest(binding),bindings=binding,requester_id=custody._requester,
        purpose="independent-reproduction",now=now if fresh else issued,max_age_seconds=86400)

def seal_archive(directory,*,custody,options,reviewer_keys,review_attestation):
    """Persist a separate fresh review; never overwrite an earlier review."""
    _validate(custody,options,reviewer_keys)
    binding,receipt=_inspect(directory,custody=custody,options=options,reviewed=False,fresh=True)
    _review(review_attestation,binding,receipt,custody=custody,reviewer_keys=reviewer_keys,fresh=True)
    directory=private_directory(directory)
    encoded=canonical(review_attestation)
    if len(encoded)>MAX_RECEIPT:
        raise ValueError("review receipt exceeds bound")
    with custody._transaction() as db:
        latest=custody._read(db)
        custody._verify(latest,fresh=True)
        if latest["bindings"]!=receipt["bindings"]:
            raise PermissionError("custody tip changed during archive review")
        _write(directory/"review.json",encoded)
        sync_directory(directory)
    return inspect_archive(directory,custody=custody,options=options,reviewer_keys=reviewer_keys)

def inspect_archive(directory,*,custody,options,reviewer_keys):
    """Verify historical archive and review, including after freshness expires.

    Still requires configured pinned trust and the previous encryption key.
    This is not an authorization to reopen a live writer or restore an old tip.
    """
    _validate(custody,options,reviewer_keys)
    binding,receipt=_inspect(directory,custody=custody,options=options,reviewed=True,fresh=False)
    review=_read_json(Path(directory)/"review.json")
    verified=_review(review,binding,receipt,custody=custody,reviewer_keys=reviewer_keys,fresh=False)
    return {"schema":"wilborn-reviewed-history-archive/1","data_class":"synthetic",
            "archive_binding":binding,"review_statement_sha256":verified["statement_sha256"],
            "encrypted_history_verified":True,"historical_receipts_verified":True,
            "current_recovery_authorized":False,"deletion_authorized":False,
            "activation_authorized":False,"execution_authorized":False,"production_qualified":False}
