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
MAX_BYTES=32768
MAX_REVISION=1024

def integer(value,minimum=0,maximum=MAX_REVISION):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError("Invalid bounded summary count")
    return value

def validate_snapshot(value):
    if type(value) is not dict or set(value)!=FIELDS:
        raise ValueError("Exact security summary fields required")
    if (value["schema"]!="merlin-studio-security-summary/1" or
            value["environment"]!="demo" or value["data_class"]!="synthetic" or
            value["execution_authorized"] is not False or value["production_qualified"] is not False):
        raise ValueError("Only non-authorizing synthetic security summaries are accepted")
    revision=integer(value["revision"],1)
    events=integer(value["accepted_events"])
    reviews=integer(value["operator_reviews"])
    if revision!=events+reviews+1:
        raise ValueError("Invalid summary revision")
    for key,allowed in (("counts",KINDS),("pending_alerts",KINDS|CORRELATIONS)):
        counts=value[key]
        if type(counts) is not dict or not set(counts)<=allowed:
            raise ValueError("Unrecognized summary categories")
        for count in counts.values():
            integer(count,1,events)
    if sum(value["counts"].values())!=events:
        raise ValueError("Invalid event count")
    active=value["active_correlations"]
    if type(active) is not list or any(type(x) is not str or x not in CORRELATIONS for x in active):
        raise ValueError("Invalid correlation categories")
    if active!=sorted(set(active)):
        raise ValueError("Duplicate or unordered correlations")
    anchor=integer(value["external_anchor_revision"],0,revision)
    if value["external_anchor_verified"] is not (anchor>0):
        raise ValueError("Invalid reported anchor status")
    recent=value["recent_incidents"]
    if type(recent) is not list or len(recent)!=min(20,revision-1):
        raise ValueError("Invalid recent history length")
    expected=revision-len(recent)+1
    for record in recent:
        if type(record) is not dict or integer(record.get("revision"),2)!=expected:
            raise ValueError("Invalid incident order")
        expected+=1
        if record.get("type")=="event":
            if set(record)!={"revision","type","kind"} or type(record["kind"]) is not str or record["kind"] not in KINDS:
                raise ValueError("Invalid event summary")
        elif record.get("type")=="operator_review":
            if set(record)!={"revision","type"}:
                raise ValueError("Invalid review summary")
        else:
            raise ValueError("Invalid incident type")
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
    timeline="".join("<tr><td>"+str(e["revision"])+"</td><td>"+escape(e.get("kind",e["type"]))+"</td></tr>" for e in reversed(s["recent_incidents"])) or '<tr><td colspan="2">None</td></tr>'
    anchor=("Host reports signed anchor revision "+str(s["external_anchor_revision"]) if s["external_anchor_verified"] else "No independent anchor reported")
    return (head+'<p>Revision '+str(s["revision"])+' · Events '+str(s["accepted_events"])+' · Reviews '+str(s["operator_reviews"])+'</p>'
        '<h2>Pending alerts</h2><table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>'+rows(s["pending_alerts"])+'</tbody></table>'
        '<h2>Event counts</h2><table><thead><tr><th>Category</th><th>Count</th></tr></thead><tbody>'+rows(s["counts"])+'</tbody></table>'
        '<h2>Reported active correlations</h2><p>'+escape(", ".join(s["active_correlations"]) or "None")+'</p>'
        '<h2>Recent incidents</h2><table><thead><tr><th>Revision</th><th>Category</th></tr></thead><tbody>'+timeline+'</tbody></table>'
        '<h2>Rollback evidence</h2><p>'+escape(anchor)+'</p>'
        '<p class="note">To refresh, export a new trusted host summary and restart Studio. This view cannot acknowledge alerts, change policy, or authorize actions.</p></main></html>')
