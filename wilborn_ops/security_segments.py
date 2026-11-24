"""Read-only, bounded review of a synthetic staged rotation's two segments.

The predecessor archive and the successor genesis are independently checked
by the existing rotation boundary. This is a pre-activation view: it does not
verify a writer handover, an active historical chain, or operational custody.
The trusted host must quiesce writers throughout inspection. Before/after
checks detect observed changes; they do not acquire a cross-ledger lease.
"""
from pathlib import Path

from .security_cutover import _genesis, _quiet
from .security_rotation import inspect_rotation

MAX_DISPLAY_HISTORY = 20


def _segment(index, role, report, history):
    return {
        "segment_index": index,
        "role": role,
        "ledger_id": report["ledger_id"],
        "state_sha256": report["state_sha256"],
        **{key: report[key] for key in (
            "revision", "accepted_events", "operator_reviews", "counts",
            "pending_alerts", "active_correlations", "external_anchor_revision",
            "external_anchor_verified")},
        "history_entries_verified": len(history["entries"]),
    }


def inspect_staged_segments(source, archive, directory, *, predecessor, successor,
                            old_options, new_options, archive_review_keys,
                            reserve_revisions, rotation_review_keys,
                            history_limit=MAX_DISPLAY_HISTORY):
    """Verify and summarize one reviewed predecessor-to-genesis transition.

    Segment indices are zero-based and chronological: predecessor archive is
    0, untouched successor genesis is 1. At most 20 incident summaries are
    returned overall, though complete histories are verified. The successor
    has no copied or reconstructed predecessor events. The retained pending
    alerts remain attached to the predecessor and are also totaled explicitly.

    Inputs are host-configured paths, trust and keys, never imported claims.
    Keys, receipt bodies, signatures and raw event payloads are not returned.
    The result still contains ledger identities and checkpoint digests; use a
    separate minimized export boundary for a portable Studio display.
    """
    if type(history_limit) is not int or not 0 <= history_limit <= MAX_DISPLAY_HISTORY:
        raise ValueError("history limit must be an integer between 0 and 20")
    options = dict(predecessor=predecessor, successor=successor,
                   old_options=old_options, new_options=new_options,
                   archive_review_keys=archive_review_keys,
                   reserve_revisions=reserve_revisions,
                   rotation_review_keys=rotation_review_keys)
    reviewed = inspect_rotation(source, archive, directory, **options)
    old_report, old_history = predecessor.open_ledger(
        _quiet(source), **old_options).review_snapshot()
    new_report, new_history = successor.open_ledger(
        _quiet(Path(directory) / "successor.sqlite3"), **new_options).review_snapshot()
    binding = reviewed["review_bindings"]
    if (old_report["ledger_id"] != binding["predecessor_ledger_id"]
            or old_report["revision"] != binding["predecessor_revision"]
            or old_report["state_sha256"] != binding["predecessor_state_sha256"]
            or old_report["accepted_events"] != reviewed["predecessor_events"]
            or old_report["operator_reviews"] != reviewed["predecessor_reviews"]
            or old_report["pending_alerts"] != reviewed["predecessor_unresolved_alerts"]
            or old_report["external_anchor_revision"] != old_report["revision"]
            or not old_report["external_anchor_verified"]
            or len(old_history["entries"]) != old_report["revision"] - 1):
        raise PermissionError("predecessor snapshot differs from reviewed rotation")
    if (new_report["ledger_id"] != binding["successor_ledger_id"]
            or _genesis(new_report) != binding["successor_genesis_sha256"]
            or new_history["entries"]
            or new_report["external_anchor_revision"] != 1
            or not new_report["external_anchor_verified"]):
        raise PermissionError("successor snapshot must match reviewed anchored genesis")
    if inspect_rotation(source, archive, directory, **options) != reviewed:
        raise PermissionError("rotation changed during segment inspection")

    segments = [_segment(0, "predecessor_archive", old_report, old_history),
                _segment(1, "successor_genesis", new_report, new_history)]
    # Revision numbers are local to a ledger. Keep the segment identity on
    # every displayed entry; never renumber the successor or migrate events.
    entries = []
    for segment, history in zip(segments, (old_history, new_history)):
        for entry in history["entries"]:
            entries.append({
                "segment_index": segment["segment_index"],
                "ledger_id": segment["ledger_id"],
                "revision": entry["revision"],
                "type": entry["type"],
                **({"kind": entry["kind"]} if entry["type"] == "event" else {}),
            })
    recent = entries[-history_limit:] if history_limit else []
    return {
        "schema": "wilborn-staged-segment-review/1",
        "environment": "demo",
        "data_class": "synthetic",
        "review_scope": "staged_rotation",
        "segments": segments,
        "accepted_events": old_report["accepted_events"],
        "operator_reviews": old_report["operator_reviews"],
        "counts": dict(old_report["counts"]),
        "pending_alerts": dict(old_report["pending_alerts"]),
        "recent_incidents": recent,
        "history_entries_verified": len(entries),
        "history_entries_displayed": len(recent),
        "history_display_truncated": len(recent) < len(entries),
        "continuity_sha256": binding["continuity_sha256"],
        "rotation_review_statement_sha256": reviewed["review_statement_sha256"],
        "predecessor_archive_verified": True,
        "successor_genesis_verified": True,
        "predecessor_alerts_resolved": False,
        "history_reconstructed": False,
        "writer_handover_verified": False,
        "active_history_verified": False,
        "activation_authorized": False,
        "deletion_authorized": False,
        "execution_authorized": False,
        "production_qualified": False,
    }
