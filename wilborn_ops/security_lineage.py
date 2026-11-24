"""Bounded host review of an actually verified active synthetic ledger lineage.

The configured handover owns ancestry verification and lock ordering. This
boundary validates the complete returned history and preserves segment-local
identities before selecting the display suffix. It is not production custody,
permission to mutate a ledger, or authentication of an exported Studio file.
"""
from collections import Counter

from .security_handover import WriterHandover
from .security_ledger import MAX_HISTORY,MAX_CLOCK,ALERTS,_uuid,_integer,_hex
from .security_monitor import KINDS,RULES,MAX_COUNTER
from .security_segments import _segment,MAX_DISPLAY_HISTORY

MAX_SEGMENTS=8


def _mapping(value,allowed,maximum):
    if type(value) is not dict or not set(value)<=allowed:
        raise ValueError("invalid lineage count categories")
    for count in value.values():
        _integer(count,1,maximum)


def _validate_segment(report,history,*,archived):
    if (type(report) is not dict or report.get("schema")!="wilborn-security-review-report/1"
            or report.get("environment")!="demo" or report.get("data_class")!="synthetic"
            or report.get("execution_authorized") is not False
            or report.get("production_qualified") is not False):
        raise PermissionError("synthetic non-authorizing lineage report required")
    _uuid(report["ledger_id"])
    _hex(report["state_sha256"])
    revision=_integer(report["revision"],1,MAX_HISTORY)
    events=_integer(report["accepted_events"],0,MAX_HISTORY-1)
    reviews=_integer(report["operator_reviews"],0,MAX_HISTORY-1)
    if revision!=1+events+reviews:
        raise ValueError("lineage segment revision invariant")
    _mapping(report["counts"],KINDS,events)
    _mapping(report["pending_alerts"],ALERTS,events)
    if sum(report["counts"].values())!=events:
        raise ValueError("lineage segment event count invariant")
    correlations=report["active_correlations"]
    if (type(correlations) is not list or any(type(x) is not str or x not in RULES for x in correlations)
            or correlations!=sorted(set(correlations))):
        raise ValueError("invalid lineage correlation categories")
    anchor=_integer(report["external_anchor_revision"],1,revision)
    if report["external_anchor_verified"] is not True or (archived and anchor!=revision):
        raise PermissionError("current lineage custody and exact archived tips required")
    if (type(history) is not dict or set(history)!={"schema","environment","data_class",
            "revision","entries","execution_authorized"}
            or history["schema"]!="wilborn-security-history/1"
            or history["environment"]!="demo" or history["data_class"]!="synthetic"
            or history["execution_authorized"] is not False or history["revision"]!=revision
            or type(history["entries"]) is not list or len(history["entries"])!=revision-1):
        raise PermissionError("complete coherent lineage history required")
    _integer(history["revision"],1,MAX_HISTORY)
    counted=Counter()
    event_sequence=0
    review_count=0
    last_received=0
    for expected,entry in enumerate(history["entries"],2):
        if type(entry) is not dict or entry.get("revision")!=expected:
            raise PermissionError("lineage history gap or order mismatch")
        _integer(entry["revision"],2,MAX_HISTORY)
        _hex(entry["state_sha256"])
        received=_integer(entry["received_at_utc"],last_received,MAX_CLOCK)
        last_received=received
        common={"revision","type","state_sha256","received_at_utc"}
        if entry["type"]=="event":
            if (set(entry)!=common|{"kind","sequence","alerts"}
                    or type(entry["kind"]) is not str or entry["kind"] not in KINDS):
                raise PermissionError("invalid lineage event summary")
            event_sequence+=1
            if _integer(entry["sequence"],1,events)!=event_sequence:
                raise PermissionError("lineage event sequence mismatch")
            _mapping(entry["alerts"],ALERTS,events)
            counted[entry["kind"]]+=1
        elif entry["type"]=="operator_review":
            if set(entry)!=common|{"acknowledged"} or not entry["acknowledged"]:
                raise PermissionError("invalid lineage operator review")
            _mapping(entry["acknowledged"],ALERTS,events)
            review_count+=1
        else:
            raise ValueError("unknown lineage history entry")
    if (dict(counted)!=report["counts"] or event_sequence!=events or review_count!=reviews
            or (history["entries"] and history["entries"][-1]["state_sha256"]!=report["state_sha256"])):
        raise PermissionError("lineage report differs from complete history")


def inspect_active_lineage(handover,*,history_limit=MAX_DISPLAY_HISTORY):
    """Verify 2..8 ordered segments through the configured current handover.

    Core lineage_snapshot verifies every retained edge, grant, proof and current
    custodian under the ancestor coordinator locks. No caller-supplied report
    or omitted ancestor can stand in for that operation. All histories are
    checked even when the display window is zero. Returned identities/digests
    are host-only; use studio_lineage_snapshot for a minimized portable view.
    """
    if type(history_limit) is not int or not 0<=history_limit<=MAX_DISPLAY_HISTORY:
        raise ValueError("history limit must be an integer between 0 and 20")
    if type(handover) is not WriterHandover:
        raise TypeError("configured current WriterHandover required")
    snapshot=handover.lineage_snapshot()
    if type(snapshot) is not dict or set(snapshot)!={"ownership_epoch","segments"}:
        raise PermissionError("exact verified lineage snapshot required")
    epoch=_integer(snapshot["ownership_epoch"],1,MAX_COUNTER)
    records=snapshot["segments"]
    if type(records) is not list or not 2<=len(records)<=MAX_SEGMENTS:
        raise ValueError("bounded complete lineage of 2..8 segments required")
    segments=[]
    entries=[]
    identities=set()
    counts=Counter()
    pending=Counter()
    for index,record in enumerate(records):
        if type(record) is not tuple or len(record)!=2:
            raise ValueError("verified report and complete history pair required")
        report,history=record
        archived=index<len(records)-1
        _validate_segment(report,history,archived=archived)
        if report["ledger_id"] in identities:
            raise PermissionError("duplicate or cyclic lineage segment")
        identities.add(report["ledger_id"])
        role="archived_predecessor" if archived else "active_successor"
        segment=_segment(index,role,report,history)
        segments.append(segment)
        counts.update(report["counts"])
        pending.update(report["pending_alerts"])
        for entry in history["entries"]:
            entries.append({"segment_index":index,"ledger_id":report["ledger_id"],
                "revision":entry["revision"],"type":entry["type"],
                **({"kind":entry["kind"]} if entry["type"]=="event" else {})})
    recent=entries[-history_limit:] if history_limit else []
    return {"schema":"wilborn-active-lineage-review/1","environment":"demo",
        "data_class":"synthetic","review_scope":"active_lineage",
        "ownership_epoch":epoch,"active_segment_index":len(segments)-1,
        "segments":segments,"accepted_events":sum(s["accepted_events"] for s in segments),
        "operator_reviews":sum(s["operator_reviews"] for s in segments),
        "counts":dict(sorted(counts.items())),"pending_alerts":dict(sorted(pending.items())),
        "recent_incidents":recent,"history_entries_verified":len(entries),
        "history_entries_displayed":len(recent),"history_display_truncated":len(recent)<len(entries),
        "writer_handover_verified":True,"active_history_verified":True,
        "predecessor_alerts_resolved":False,"history_reconstructed":False,
        "activation_authorized":False,"deletion_authorized":False,
        "execution_authorized":False,"production_qualified":False}
