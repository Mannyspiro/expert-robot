"""Read-only display of an explicitly host-supplied synthetic summary.

The import validates structure only; it does not verify a signature, attest
real-world telemetry, or provide authorization. No network or ledger access.
"""
from html import escape
import json
import os
from pathlib import Path
import stat

KINDS=frozenset({"auth_failure","tool_denied","provenance_rejected","rate_limit",
    "integrity_failure","unexpected_tool","artex_guard_marker","artex_recording_ca",
    "artex_update_indicator","artex_inbound_indicator"})
CORRELATIONS=frozenset({"authentication_denial_burst","tool_policy_denial_burst",
    "artex_guard_marker_burst"})
FIELDS=frozenset({"schema","environment","data_class","execution_authorized",
    "production_qualified","revision","accepted_events","operator_reviews","counts",
    "pending_alerts","active_correlations","external_anchor_revision",
    "external_anchor_verified","recent_incidents"})
ROTATION_FIELDS=frozenset({"schema","environment","data_class","execution_authorized",
    "production_qualified","activation_authorized","writer_handover_verified",
    "review_scope","accepted_events","operator_reviews","counts","pending_alerts",
    "segments","recent_incidents"})
SEGMENT_FIELDS=frozenset({"segment_index","role","revision","accepted_events",
    "operator_reviews","counts","pending_alerts","active_correlations",
    "external_anchor_revision","external_anchor_verified"})
MAX_BYTES=32768
MAX_REVISION=1024

def integer(value,minimum=0,maximum=MAX_REVISION):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError("Invalid bounded summary count")
    return value

def _validate_counts(value,events):
    for key,allowed in (("counts",KINDS),("pending_alerts",KINDS|CORRELATIONS)):
        counts=value[key]
        if type(counts) is not dict or not set(counts)<=allowed:
            raise ValueError("Unrecognized summary categories")
        for count in counts.values():
            integer(count,1,events)
    if sum(value["counts"].values())!=events:
        raise ValueError("Invalid event count")

def _validate_segment_state(value):
    revision=integer(value["revision"],1)
    events=integer(value["accepted_events"])
    reviews=integer(value["operator_reviews"])
    if revision!=events+reviews+1:
        raise ValueError("Invalid summary revision")
    _validate_counts(value,events)
    active=value["active_correlations"]
    if type(active) is not list or any(type(x) is not str or x not in CORRELATIONS for x in active):
        raise ValueError("Invalid correlation categories")
    if active!=sorted(set(active)):
        raise ValueError("Duplicate or unordered correlations")
    anchor=integer(value["external_anchor_revision"],0,revision)
    if value["external_anchor_verified"] is not (anchor>0):
        raise ValueError("Invalid reported anchor status")
    return revision

def _validate_incident(record,extra_fields=frozenset()):
    fields={"revision","type"}|extra_fields
    if record.get("type")=="event":
        if set(record)!=fields|{"kind"} or type(record["kind"]) is not str or record["kind"] not in KINDS:
            raise ValueError("Invalid event summary")
    elif record.get("type")=="operator_review":
        if set(record)!=fields:
            raise ValueError("Invalid review summary")
    else:
        raise ValueError("Invalid incident type")

def _validate_single_snapshot(value):
    revision=_validate_segment_state(value)
    recent=value["recent_incidents"]
    if type(recent) is not list or len(recent)!=min(20,revision-1):
        raise ValueError("Invalid recent history length")
    expected=revision-len(recent)+1
    for record in recent:
        if type(record) is not dict or integer(record.get("revision"),2)!=expected:
            raise ValueError("Invalid incident order")
        expected+=1
        _validate_incident(record)

def _validate_rotation_snapshot(value):
    if (value["activation_authorized"] is not False or value["writer_handover_verified"] is not False
            or value["review_scope"]!="staged_rotation"):
        raise ValueError("Only non-activating staged rotation summaries are accepted")
    segments=value["segments"]
    if type(segments) is not list or len(segments)!=2:
        raise ValueError("Exactly two ordered security segments required")
    roles=("predecessor_archive","successor_genesis")
    expected=[]
    for index,segment in enumerate(segments):
        if type(segment) is not dict or set(segment)!=SEGMENT_FIELDS:
            raise ValueError("Exact security segment fields required")
        if integer(segment["segment_index"],0,1)!=index or segment["role"]!=roles[index]:
            raise ValueError("Invalid segment order or role")
        revision=_validate_segment_state(segment)
        if segment["external_anchor_revision"]!=revision or segment["external_anchor_verified"] is not True:
            raise ValueError("Each staged segment requires its current reported anchor")
        if index==1 and (revision!=1 or segment["counts"] or segment["pending_alerts"]
                or segment["active_correlations"]):
            raise ValueError("Successor must remain an untouched anchored genesis")
        expected.extend((index,number) for number in range(2,revision+1))
    for key in ("accepted_events","operator_reviews"):
        count=integer(value[key],0,2*(MAX_REVISION-1))
        if count!=sum(segment[key] for segment in segments):
            raise ValueError("Aggregate security count differs from segments")
    _validate_counts(value,value["accepted_events"])
    for key in ("counts","pending_alerts"):
        combined={}
        for segment in segments:
            for category,count in segment[key].items():
                combined[category]=combined.get(category,0)+count
        if value[key]!=combined:
            raise ValueError("Aggregate security categories differ from segments")
    expected=expected[-20:]
    recent=value["recent_incidents"]
    if type(recent) is not list or len(recent)!=len(expected):
        raise ValueError("Invalid recent segmented history length")
    observed=[{"events":{},"reviews":0} for _ in segments]
    for record,(index,revision) in zip(recent,expected):
        if (type(record) is not dict or integer(record.get("segment_index"),0,1)!=index
                or integer(record.get("revision"),2)!=revision):
            raise ValueError("Invalid segmented incident order")
        _validate_incident(record,{"segment_index"})
        if record["type"]=="event":
            kind=record["kind"]
            observed[index]["events"][kind]=observed[index]["events"].get(kind,0)+1
        else:
            observed[index]["reviews"]+=1
    for segment,seen in zip(segments,observed):
        if (seen["reviews"]>segment["operator_reviews"] or
                any(count>segment["counts"].get(kind,0) for kind,count in seen["events"].items())):
            raise ValueError("Recent incidents exceed segment counts")

def validate_snapshot(value):
    if type(value) is not dict:
        raise ValueError("Exact security summary fields required")
    schema=value.get("schema")
    fields=FIELDS if schema=="merlin-studio-security-summary/1" else ROTATION_FIELDS if schema=="merlin-studio-security-summary/2" else None
    if fields is None or set(value)!=fields:
        raise ValueError("Exact security summary fields required")
    if (value["environment"]!="demo" or value["data_class"]!="synthetic" or
            value["execution_authorized"] is not False or value["production_qualified"] is not False):
        raise ValueError("Only non-authorizing synthetic security summaries are accepted")
    if schema=="merlin-studio-security-summary/1":
        _validate_single_snapshot(value)
    else:
        _validate_rotation_snapshot(value)
    return value

def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("Duplicate summary field")
        result[key]=value
    return result

def load_snapshot(path):
    """A host-controlled path, never supplied via a request or model tool."""
    path=Path(path)
    if path.is_symlink():
        raise ValueError("Security summary must be a regular file")
    flags=os.O_RDONLY | getattr(os,"O_NOFOLLOW",0) | getattr(os,"O_NONBLOCK",0) | getattr(os,"O_BINARY",0)
    fd=os.open(path,flags)
    try:
        metadata=os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or not 0<metadata.st_size<=MAX_BYTES:
            raise ValueError("Invalid security summary file")
        with os.fdopen(fd,"rb",closefd=False) as stream:
            raw=stream.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES:
            raise ValueError("Oversized security summary")
        return validate_snapshot(json.loads(raw.decode("utf-8"),object_pairs_hook=_unique))
    finally:
        os.close(fd)

def render_snapshot(summary):
    head=('<!doctype html><html lang="en"><meta charset="utf-8">'
          '<meta name="viewport" content="width=device-width, initial-scale=1">'
          '<title>Merlin Studio security review</title><style>'
          'body{font:16px system-ui,sans-serif;background:#1b1d19;color:#efeee7;max-width:850px;margin:32px auto;padding:0 20px}'
          'a{color:#e8c7aa}h1{font-size:28px}h2{font-size:18px;margin-top:28px}'
          'table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:8px;border-bottom:1px solid #35392f}'
          '.note{color:#a4aa9a;line-height:1.6}</style><main><p><a href="/studio/">Back to Studio</a></p>'
          '<h1>Security review</h1><p class="note">SYNTHETIC DEMO · Imported host snapshot, not live monitoring or independently verified security evidence. No execution authorized.</p>')
    if summary is None:
        return head+'<p>No host security summary configured. Start Studio with an approved synthetic summary to review.</p></main></html>'
    s=validate_snapshot(summary)
    def rows(mapping):
        return "".join("<tr><td>"+escape(k)+"</td><td>"+str(v)+"</td></tr>" for k,v in sorted(mapping.items())) or '<tr><td colspan="2">None</td></tr>'
    if s["schema"]=="merlin-studio-security-summary/2":
        def table(title,mapping):
            return ('<h3>'+title+'</h3><table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>'
                +rows(mapping)+'</tbody></table>')
        sections=[]
        labels=("Predecessor archive","Successor genesis")
        for segment in s["segments"]:
            index=segment["segment_index"]
            sections.append('<section aria-labelledby="segment-'+str(index)+'"><h2 id="segment-'+str(index)+'">'
                +labels[index]+' · Segment '+str(index)+'</h2><p>Segment revision '+str(segment["revision"])
                +' · Events '+str(segment["accepted_events"])+' · Reviews '+str(segment["operator_reviews"])+'</p>'
                +table("Pending predecessor alerts" if index==0 else "Pending successor alerts",segment["pending_alerts"])
                +table("Segment event counts",segment["counts"])
                +'<h3>Reported active correlations</h3><p>'+escape(", ".join(segment["active_correlations"]) or "None")+'</p>'
                +'<p>Host reports signed anchor revision '+str(segment["external_anchor_revision"])+' for this segment.</p></section>')
        timeline="".join('<tr><td>'+labels[e["segment_index"]]+' (segment '+str(e["segment_index"])+')</td><td>'
            +str(e["revision"])+'</td><td>'+escape(e.get("kind",e["type"]))+'</td></tr>' for e in reversed(s["recent_incidents"])) or '<tr><td colspan="3">None</td></tr>'
        return (head+'<h2>Staged rotation review</h2><p>Writer handover not verified · Successor not activated</p>'
            '<p class="note">Host-reported continuity for two staged segments. Studio validates the summary structure; it does not independently verify the ledger, signatures, or anchors. Each revision belongs to its segment.</p>'
            '<p>Total events '+str(s["accepted_events"])+' · Total reviews '+str(s["operator_reviews"])+'</p>'
            +table("Pending alerts across both segments",s["pending_alerts"])
            +table("Event counts across both segments",s["counts"])+"".join(sections)
            +'<h2>Recent incidents</h2><table><thead><tr><th>Segment</th><th>Segment revision</th><th>Category</th></tr></thead><tbody>'
            +timeline+'</tbody></table><p class="note">Pending predecessor alerts remain unresolved. This view cannot activate a successor, transfer a writer, acknowledge alerts, or authorize actions. To refresh, export a new trusted host summary and restart Studio.</p></main></html>')
    timeline="".join("<tr><td>"+str(e["revision"])+"</td><td>"+escape(e.get("kind",e["type"]))+"</td></tr>" for e in reversed(s["recent_incidents"])) or '<tr><td colspan="2">None</td></tr>'
    anchor=("Host reports signed anchor revision "+str(s["external_anchor_revision"]) if s["external_anchor_verified"] else "No independent anchor reported")
    return (head+'<p>Revision '+str(s["revision"])+' · Events '+str(s["accepted_events"])+' · Reviews '+str(s["operator_reviews"])+'</p>'
        '<h2>Pending alerts</h2><table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>'+rows(s["pending_alerts"])+'</tbody></table>'
        '<h2>Event counts</h2><table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>'+rows(s["counts"])+'</tbody></table>'
        '<h2>Reported active correlations</h2><p>'+escape(", ".join(s["active_correlations"]) or "None")+'</p>'
        '<h2>Recent incidents</h2><table><thead><tr><th>Revision</th><th>Category</th></tr></thead><tbody>'+timeline+'</tbody></table>'
        '<h2>Rollback evidence</h2><p>'+escape(anchor)+'</p>'
        '<p class="note">To refresh, export a new trusted host summary and restart Studio. This view cannot acknowledge alerts, change policy, or authorize actions.</p></main></html>')
