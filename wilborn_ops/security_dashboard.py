"""Local static operator report for synthetic telemetry; no web service."""
from html import escape
from .security_ledger import SecurityLedger

def render_operator_report(ledger):
    if type(ledger) is not SecurityLedger:
        raise TypeError("trusted host ledger required")
    report=ledger.report()
    history=ledger.history()
    if history["revision"]!=report["revision"]:
        raise RuntimeError("checkpoint changed during review; refresh report")
    entries=history["entries"][-20:]
    timeline="".join("<tr><td>"+str(e["revision"])+"</td><td>"+escape(e.get("kind",e["type"]))+"</td></tr>" for e in reversed(entries)) or '<tr><td colspan="2">None</td></tr>'
    anchored="Signed revision "+str(report["external_anchor_revision"]) if report["external_anchor_verified"] else "No independent anchor configured"
    def rows(mapping):
        if not mapping:
            return '<tr><td colspan="2">None</td></tr>'
        return "".join("<tr><td>"+escape(k)+"</td><td>"+str(v)+"</td></tr>"
                       for k,v in sorted(mapping.items()))
    active=", ".join(report["active_correlations"]) or "None"
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'">'
            '<title>Merlin synthetic security review</title>'
            '<style>body{font:16px system-ui,sans-serif;max-width:860px;margin:36px auto;padding:0 20px;color:#172534;background:#fff}h1{font-size:28px}h2{font-size:19px;margin-top:30px}'
            'table{width:100%;border-collapse:collapse}td,th{text-align:left;border-bottom:1px solid #d8dee5;padding:10px}td:last-child,th:last-child{text-align:right}p{line-height:1.5}.note{color:#536373}code{overflow-wrap:anywhere}</style>'
            '<main><h1>Merlin security review</h1><p class="note">SYNTHETIC DEMO — not a production security assessment. No execution authorized.</p>'
            '<p>Accepted events: '+str(report["accepted_events"])+' | Operator reviews: '+str(report["operator_reviews"])+'</p>'
            '<h2>Pending operator review</h2><table><thead><tr><th>Alert</th><th>Count</th></tr></thead><tbody>'+rows(report["pending_alerts"])+'</tbody></table>'
            '<h2>Event counts</h2><table><thead><tr><th>Event</th><th>Count</th></tr></thead><tbody>'+rows(report["counts"])+'</tbody></table>'
            '<h2>Current correlations</h2><p>'+escape(active)+'</p>'
            '<h2>Recent incident history</h2><table><thead><tr><th>Revision</th><th>Event or review</th></tr></thead><tbody>'+timeline+'</tbody></table>'
            '<h2>Independent rollback evidence</h2><p>'+escape(anchored)+'</p>'
            '<h2>Checkpoint identity</h2><p>Ledger: <code>'+escape(report["ledger_id"])+'</code><br>Revision: '+str(report["revision"])+'<br>SHA-256: <code>'+escape(report["state_sha256"])+'</code></p>'
            '<p class="note">Acknowledgement requires a separate signed operator statement against the exact current checkpoint. This report never changes authorization or confirms compromise.</p></main></html>')
