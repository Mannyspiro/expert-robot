"""Reviewed synthetic segment rotation staging; never activates a writer.

The predecessor's full encrypted archive and unresolved alert counts are
retained. A distinct successor starts at genesis. Review requires current
anchors and verifies an exact sealed continuity link. Writers must be
quiesced by the trusted host throughout staging and review.
"""
from datetime import datetime,timezone
from pathlib import Path

from python.merlin.artifact_ref import ArtifactRef
from .attestation_boundary import canonical,digest,fresh_attestation,separated_trust
from .security_archive import inspect_archive,retention_status,_read_json,_issued
from .security_cutover import _validate,_quiet,_write,_genesis
from .security_ledger import SecurityLedger
from .security_recovery import private_directory,sync_directory
from .titan_envelope import seal_demo,open_demo

CLAIM="wilborn:security:segment-rotation-review:v1"

def _roles(predecessor,successor,old_options,new_options,archive_review_keys,rotation_review_keys=None):
    _validate(predecessor,successor,old_options,new_options)
    # A rotation fixture uses separately configured role identities and keys.
    roles=[predecessor._trust,successor._trust,old_options["sensor_keys"],
           old_options["operator_keys"],new_options["sensor_keys"],
           new_options["operator_keys"],archive_review_keys]
    if rotation_review_keys is not None:
        roles.append(rotation_review_keys)
    for index,left in enumerate(roles):
        for right in roles[index+1:]:
            separated_trust(left,right)

def _predecessor(source,archive,*,custody,options,archive_review_keys,reserve_revisions):
    ledger=custody.open_ledger(_quiet(source),**options)
    report,history=ledger.review_snapshot()
    advisory=retention_status(ledger,reserve_revisions=reserve_revisions)
    if advisory["revision"]!=report["revision"] or not advisory["archive_review_due"]:
        raise PermissionError("stable predecessor at declared retention threshold required")
    reviewed=inspect_archive(archive,custody=custody,options=options,
                             reviewer_keys=archive_review_keys)
    binding=reviewed["archive_binding"]
    retained=custody.latest()["bindings"]
    if (binding["ledger_id"]!=report["ledger_id"] or
            binding["revision"]!=report["revision"] or
            binding["state_sha256"]!=report["state_sha256"] or
            retained["revision"]!=report["revision"] or
            retained["state_sha256"]!=report["state_sha256"] or
            len(history["entries"])!=report["revision"]-1):
        raise PermissionError("reviewed archive must represent exact current anchored predecessor")
    return {"ledger_id":report["ledger_id"],"revision":report["revision"],
            "state_sha256":report["state_sha256"],"accepted_events":report["accepted_events"],
            "operator_reviews":report["operator_reviews"],"counts":report["counts"],
            "unresolved_alerts":report["pending_alerts"],
            "history_sha256":digest(history),"archive_binding":binding,
            "archive_review_statement_sha256":reviewed["review_statement_sha256"]}

def _link(old,successor,genesis,reserve):
    return {"schema":"wilborn-segment-continuity/1","environment":"demo",
            "data_class":"synthetic","predecessor":old,
            "successor_ledger_id":successor._id,"successor_genesis_sha256":genesis,
            "reserve_revisions":reserve,"predecessor_alerts_resolved":False,
            "history_reconstructed":False,"deletion_authorized":False,
            "activation_authorized":False,"execution_authorized":False}

def _ref(successor,link):
    return ArtifactRef("wilborn-demo","security/wilborn/synthetic_fixture/"+successor._id+"/segment-continuity",
                       1,digest(link)).to_dict()

def _binding(link):
    old=link["predecessor"]
    return {"schema":"wilborn-segment-rotation-review/1","environment":"demo",
            "data_class":"synthetic","predecessor_ledger_id":old["ledger_id"],
            "predecessor_revision":old["revision"],"predecessor_state_sha256":old["state_sha256"],
            "successor_ledger_id":link["successor_ledger_id"],
            "successor_genesis_sha256":link["successor_genesis_sha256"],
            "continuity_sha256":digest(link),"decision":"review_staged_rotation",
            "deletion_authorized":False,"activation_authorized":False,"execution_authorized":False}

def stage_rotation(source,archive,directory,*,predecessor,successor,old_options,
                   new_options,archive_review_keys,reserve_revisions):
    """Create a new genesis and sealed link, with no active-writer transition."""
    _roles(predecessor,successor,old_options,new_options,archive_review_keys)
    source=_quiet(source)
    archive=private_directory(archive)
    directory=Path(directory)
    parent=private_directory(directory.parent)
    if directory.resolve()!=directory or directory.exists() or directory.is_symlink():
        raise FileExistsError("new private stage required")
    if parent in (predecessor._directory,successor._directory,archive):
        raise PermissionError("stage outside archive and custody directories")
    with successor._transaction() as db:
        if successor._read(db,allow_empty=True) is not None:
            raise PermissionError("successor custody must start empty")
    options=dict(custody=predecessor,options=old_options,archive_review_keys=archive_review_keys,
                 reserve_revisions=reserve_revisions)
    old=_predecessor(source,archive,**options)
    directory.mkdir(mode=0o700)
    ledger=SecurityLedger(directory/"successor.sqlite3",ledger_id=successor._id,
                requester_id=successor._requester,clock=successor._clock,create=True,**new_options)
    genesis=_genesis(ledger.report())
    if _predecessor(source,archive,**options)!=old:
        raise PermissionError("predecessor changed during rotation staging")
    link=_link(old,successor,genesis,reserve_revisions)
    sealed=seal_demo(canonical(link),artifact_ref=_ref(successor,link),
                     key_id=new_options["key_id"],master_key=new_options["master_key"])
    _write(directory/"continuity.json",canonical(sealed))
    sync_directory(directory)
    sync_directory(parent)
    return {"schema":"wilborn-staged-rotation/1","data_class":"synthetic",
            "review_bindings":_binding(link),"predecessor_unresolved_alerts":old["unresolved_alerts"],
            "successor_anchor_required":True,"review_required":True,
            "deletion_authorized":False,"activation_authorized":False,"production_qualified":False}

def _verify(source,archive,directory,*,predecessor,successor,old_options,new_options,
            archive_review_keys,reserve_revisions,rotation_review_keys,attestation,reviewed):
    _roles(predecessor,successor,old_options,new_options,archive_review_keys,rotation_review_keys)
    directory=private_directory(directory)
    expected={"successor.sqlite3","continuity.json"}|({"review.json"} if reviewed else set())
    if {p.name for p in directory.iterdir()}!=expected:
        raise ValueError("exact staged rotation inventory required")
    old=_predecessor(source,archive,custody=predecessor,options=old_options,
                     archive_review_keys=archive_review_keys,reserve_revisions=reserve_revisions)
    report=successor.open_ledger(_quiet(directory/"successor.sqlite3"),**new_options).report()
    genesis=_genesis(report)
    if report["external_anchor_revision"]!=1 or not report["external_anchor_verified"]:
        raise PermissionError("successor genesis anchor required")
    link=_link(old,successor,genesis,reserve_revisions)
    sealed=_read_json(directory/"continuity.json")
    plain=open_demo(sealed,artifact_ref=_ref(successor,link),key_id=new_options["key_id"],
                    master_key=new_options["master_key"])
    if plain!=canonical(link):
        raise PermissionError("sealed continuity differs from verified predecessors")
    binding=_binding(link)
    if reviewed:
        attestation=_read_json(directory/"review.json")
    now=datetime.fromtimestamp(successor._clock(),timezone.utc)
    earliest=max(_issued(predecessor.latest()["attestation"]),
                 _issued(successor.latest()["attestation"]),
                 _issued(_read_json(Path(archive)/"review.json")))
    if not earliest<=_issued(attestation)<=now:
        raise PermissionError("review must follow archive and current anchors")
    result=fresh_attestation(attestation,trust=rotation_review_keys,claim_id=CLAIM,
                bundle_sha256=digest(binding),bindings=binding,requester_id=successor._requester,
                purpose="independent-reproduction",now=now,max_age_seconds=86400)
    return {"schema":"wilborn-reviewed-segment-rotation/1","data_class":"synthetic",
            "review_bindings":binding,"review_statement_sha256":result["statement_sha256"],
            "predecessor_events":old["accepted_events"],"predecessor_reviews":old["operator_reviews"],
            "predecessor_unresolved_alerts":old["unresolved_alerts"],
            "predecessor_alerts_resolved":False,"predecessor_archive_verified":True,
            "successor_genesis_verified":True,"history_reconstructed":False,
            "deletion_authorized":False,"activation_authorized":False,
            "execution_authorized":False,"production_qualified":False}

def seal_rotation(source,archive,directory,*,review_attestation,**options):
    """Retain a separate signed review of the staged package without overwrite."""
    _verify(source,archive,directory,attestation=review_attestation,reviewed=False,**options)
    directory=private_directory(directory)
    _write(directory/"review.json",canonical(review_attestation))
    sync_directory(directory)
    return inspect_rotation(source,archive,directory,**options)

def inspect_rotation(source,archive,directory,**options):
    """Recheck staged review against current predecessor and untouched successor.

    This is a pre-activation check, not an historical segment chain reader.
    Current custody and quiescence are required. No writer lease is issued.
    """
    return _verify(source,archive,directory,attestation=None,reviewed=True,**options)
