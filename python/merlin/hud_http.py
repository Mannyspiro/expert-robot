"""Minimal read-only WSGI endpoint for the Merlin activity HUD.

Mount at /api/hud/activity behind the local Merlin runtime. Bind the runtime to
loopback by default; production deployments must add their normal authentication.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from merlin.hud_activity import HudActivityProjector, HudOutboxConsumer


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Merlin Research HUD</title>
<style>
:root{color-scheme:dark;font:15px/1.45 system-ui,sans-serif;background:#10131a;color:#e8edf5}
body{margin:0;padding:20px;max-width:1440px;margin-inline:auto}
header{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-size:1.5rem;margin:0}h2{font-size:1rem;margin:0 0 12px;color:#a9c4ff}
button,select{background:#26344d;color:#fff;border:1px solid #4b6288;border-radius:8px;padding:8px 12px;cursor:pointer}
#status{color:#aebbd0}
main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-top:18px}
section{background:#191f2b;border:1px solid #2c3547;border-radius:12px;padding:16px;min-width:0}
.phase{display:flex;gap:5px;flex-wrap:wrap}.phase span{font-size:.75rem;padding:5px 7px;border-radius:6px;background:#252d3d;color:#9eabc0}.phase .active{background:#31517e;color:#fff}
.item{padding:9px 0;border-bottom:1px solid #2b3445}.item:last-child{border:0}
small,.muted{color:#9ba9bf}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0 0;color:#d1d9e8}
ol,ul{padding-left:20px;margin:8px 0 0}li{margin:8px 0}
.node{display:block;width:100%;text-align:left;margin:5px 0;background:#202a3a}
#detail{margin-top:12px;max-height:260px;overflow:auto}
@media(max-width:480px){body{padding:12px}}
</style>
</head>
<body>
<header><h1>Merlin Research HUD</h1><button id="refresh" type="button">Refresh</button><span id="status">Loading canonical read-only views…</span></header>
<main>
<section><h2>Research pipeline</h2><div id="phase" class="phase"></div><div id="agents"></div></section>
<section><h2>Resources and independent verification</h2><div id="resources" class="muted">No resource sample yet.</div><pre id="verification">No independent CACE verification event yet.</pre></section>
<section><h2>Projects and research state</h2><select id="project-select" aria-label="Select project"><option>Loading projects…</option></select><div id="project-summary" class="muted"></div><h3>Artifacts</h3><ul id="artifacts"></ul><h3>Hypotheses</h3><pre id="hypotheses"></pre><h3>Outbox</h3><pre id="outbox"></pre></section>
<section><h2>Canonical knowledge graph</h2><div id="graph-summary" class="muted">Loading graph…</div><div id="nodes"></div><pre id="detail"></pre></section>
<section><h2>Event timeline</h2><ol id="timeline"></ol></section>
</main>
<script>
"use strict";
const byId = id => document.getElementById(id);
const safeText = value => value === null || value === undefined ? "—" : String(value);
let selectedProject = "";
function addItem(parent, title, detail) {
  const row = document.createElement("div");
  row.className = "item";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const small = document.createElement("div");
  small.className = "muted";
  small.textContent = detail;
  row.append(strong, small);
  parent.append(row);
}
async function loadProject(projectId) {
  if (!projectId) return;
  const response = await fetch("/api/hud/project?project_id=" + encodeURIComponent(projectId), {headers:{Accept:"application/json"}});
  if (!response.ok) throw new Error("Project query unavailable (" + response.status + ")");
  const data = await response.json();
  const project = data.project;
  byId("project-summary").textContent = project.name + " · " + project.version + " · " + project.artifacts.length + " artifacts";
  const artifacts = byId("artifacts");
  artifacts.replaceChildren();
  for (const artifact of project.artifacts || []) {
    const li = document.createElement("li");
    li.textContent = artifact.logical_path + " · " + artifact.size_bytes + " bytes · sha256 " + artifact.digest.slice(0, 16);
    artifacts.append(li);
  }
  if (!(project.artifacts || []).length) {
    const li = document.createElement("li"); li.textContent = "No registered artifacts."; artifacts.append(li);
  }
  byId("hypotheses").textContent = JSON.stringify(data.hypotheses || {items:[]}, null, 2);
  byId("outbox").textContent = JSON.stringify(data.outbox || {status:"not configured"}, null, 2);
}
async function refresh() {
  byId("status").textContent = "Refreshing…";
  try {
    const paths = ["/api/hud/activity","/api/hud/graph","/api/hud/projects","/api/hud/hypotheses","/api/hud/outbox"];
    const responses = await Promise.all(paths.map(path => fetch(path, {headers:{Accept:"application/json"}})));
    if (responses.some(response => !response.ok)) throw new Error("One or more canonical read endpoints are unavailable.");
    const [activity, graph, projects, hypotheses, outbox] = await Promise.all(responses.map(response => response.json()));
    byId("status").textContent = "Read-only · " + activity.event_count + " events · run " + safeText(activity.active_run_id);
    const phases = byId("phase"); phases.replaceChildren();
    for (const name of activity.phases || []) {
      const tag = document.createElement("span"); tag.textContent = name;
      if (name === activity.phase) tag.className = "active";
      phases.append(tag);
    }
    const agents = byId("agents"); agents.replaceChildren();
    for (const agent of activity.agents || []) addItem(agents, agent.agent_id + " · " + agent.status, agent.role + " · " + agent.activity);
    if (!(activity.agents || []).length) agents.textContent = "No agent status events yet.";
    byId("resources").textContent = JSON.stringify(activity.resources || {}, null, 2);
    byId("verification").textContent = JSON.stringify(activity.verification || {status:"not yet observed"}, null, 2);
    byId("graph-summary").textContent = (graph.nodes || []).length + " nodes · " + (graph.edges || []).length + " edges · snapshot " + safeText(graph.snapshot_sha256);
    const nodes = byId("nodes"); nodes.replaceChildren();
    for (const node of (graph.nodes || []).slice(0, 80)) {
      const button = document.createElement("button"); button.type = "button"; button.className = "node";
      button.textContent = node.label + " · " + node.node_type;
      button.addEventListener("click", async () => {
        const response = await fetch("/api/hud/node?node_id=" + encodeURIComponent(node.node_id), {headers:{Accept:"application/json"}});
        byId("detail").textContent = response.ok ? JSON.stringify(await response.json(), null, 2) : "Node detail unavailable.";
      });
      nodes.append(button);
    }
    const select = byId("project-select");
    const prior = selectedProject || select.value;
    select.replaceChildren();
    for (const project of projects.items || []) {
      const option = document.createElement("option"); option.value = project.project_id;
      option.textContent = project.name + " · " + project.artifact_count + " artifacts"; select.append(option);
    }
    if (select.options.length) {
      selectedProject = (projects.items || []).some(project => project.project_id === prior) ? prior : select.options[0].value;
      select.value = selectedProject;
      await loadProject(selectedProject);
    } else {
      byId("project-summary").textContent = "No canonical projects registered yet.";
      byId("artifacts").replaceChildren();
      byId("hypotheses").textContent = JSON.stringify(hypotheses, null, 2);
      byId("outbox").textContent = JSON.stringify(outbox, null, 2);
    }
    const timeline = byId("timeline"); timeline.replaceChildren();
    for (const event of activity.timeline || []) {
      const item = document.createElement("li");
      const title = document.createElement("strong"); title.textContent = event.label + " · " + event.source;
      const detail = document.createElement("div"); detail.className = "muted";
      detail.textContent = event.timestamp + " · " + event.summary;
      item.append(title, detail); timeline.append(item);
    }
    if (!(activity.timeline || []).length) {
      const empty = document.createElement("li"); empty.textContent = "No activity events have been projected yet."; timeline.append(empty);
    }
  } catch (error) {
    byId("status").textContent = "Read API unavailable: " + error.message;
  }
}
byId("project-select").addEventListener("change", event => {
  selectedProject = event.target.value;
  loadProject(selectedProject).catch(error => { byId("project-summary").textContent = error.message; });
});
byId("refresh").addEventListener("click", refresh);
refresh();
</script>
</body>
</html>""";


class HudActivityWSGI:
    def __init__(self, projector: HudActivityProjector,
                 consumer: HudOutboxConsumer | None = None,
                 *, read_api: Any | None = None, max_drain_per_request: int = 100):
        if not isinstance(projector, HudActivityProjector):
            raise ValueError("projector must be a HudActivityProjector")
        if isinstance(max_drain_per_request, bool) or not isinstance(max_drain_per_request, int) or not 1 <= max_drain_per_request <= 1000:
            raise ValueError("max_drain_per_request must be between 1 and 1000")
        self.projector = projector
        self.consumer = consumer
        self.read_api = read_api
        self.max_drain_per_request = max_drain_per_request

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]):
        path = environ.get("PATH_INFO")
        if path not in {"/dashboard", "/api/hud/activity", "/api/hud/graph", "/api/hud/node", "/api/hud/projects", "/api/hud/project", "/api/hud/hypotheses", "/api/hud/outbox"}:
            return self._respond(start_response, "404 Not Found",
                                 {"error": "not_found"})
        if environ.get("REQUEST_METHOD", "GET").upper() != "GET":
            return self._respond(start_response, "405 Method Not Allowed",
                                 {"error": "method_not_allowed"},
                                 extra=[("Allow", "GET")])
        if path == "/dashboard":
            return self._respond_html(start_response, DASHBOARD_HTML)
        try:
            if path in {"/api/hud/projects", "/api/hud/project",
                         "/api/hud/hypotheses", "/api/hud/outbox"}:
                if self.read_api is None:
                    return self._respond(start_response, "503 Service Unavailable",
                                         {"error": "research_query_not_configured"})
                from urllib.parse import parse_qs
                params = parse_qs(environ.get("QUERY_STRING", ""))

                def bounded_int(name: str, default: int, maximum: int) -> int:
                    raw = (params.get(name) or [str(default)])[0]
                    if not raw.isdigit() or int(raw) > maximum:
                        raise ValueError(name + " is outside the supported range")
                    return int(raw)

                if path == "/api/hud/projects":
                    limit = bounded_int("limit", 100, 500)
                    offset = bounded_int("offset", 0, 100000000)
                    return self._respond(start_response, "200 OK",
                                         self.read_api.projects(limit=limit, offset=offset))
                if path == "/api/hud/project":
                    project_id = (params.get("project_id") or [""])[0]
                    if not project_id or len(project_id) > 160:
                        return self._respond(start_response, "400 Bad Request",
                                             {"error": "project_id_required"})
                    return self._respond(start_response, "200 OK",
                                         self.read_api.project_snapshot(project_id))
                if path == "/api/hud/hypotheses":
                    limit = bounded_int("limit", 100, 500)
                    offset = bounded_int("offset", 0, 100000000)
                    status = (params.get("status") or [None])[0]
                    if self.read_api.hypotheses is None:
                        return self._respond(start_response, "200 OK", {
                            "schema": "merlin-hypothesis-page/1",
                            "items": [], "limit": limit, "offset": offset,
                            "total": 0, "configured": False,
                        })
                    return self._respond(start_response, "200 OK",
                                         self.read_api.list_hypotheses(
                                             status=status, limit=limit, offset=offset))
                if self.read_api.outbox is None:
                    return self._respond(start_response, "200 OK", {
                        "schema": "merlin-outbox-status/1",
                        "counts": {}, "configured": False,
                    })
                return self._respond(start_response, "200 OK",
                                     self.read_api.outbox_status())
            if path in {"/api/hud/graph", "/api/hud/node"}:
                if self.read_api is None:
                    return self._respond(start_response, "503 Service Unavailable",
                                         {"error": "graph_query_not_configured"})
                if path == "/api/hud/graph":
                    return self._respond(start_response, "200 OK", self.read_api.graph())
                from urllib.parse import parse_qs
                from dataclasses import asdict
                params = parse_qs(environ.get("QUERY_STRING", ""))
                node_id = (params.get("node_id") or [""])[0]
                if not node_id or len(node_id) > 160:
                    return self._respond(start_response, "400 Bad Request",
                                         {"error": "node_id_required"})
                graph_store = getattr(self.read_api, "graph_store", None)
                if graph_store is None:
                    return self._respond(start_response, "503 Service Unavailable",
                                         {"error": "knowledge_graph_not_configured"})
                node = graph_store.get_node(node_id)
                if node is None:
                    return self._respond(start_response, "404 Not Found",
                                         {"error": "node_not_found"})
                neighbors = graph_store.neighbors(node_id)
                detail = {"schema": "merlin-hud-node/1",
                          "node": asdict(node), "neighbors": neighbors}
                linked_artifacts = []
                candidates = [(node.node_id, node)]
                for edge in neighbors:
                    other_id = (edge["target_id"] if edge["source_id"] == node_id
                                else edge["source_id"])
                    other = graph_store.get_node(other_id)
                    if other is not None:
                        candidates.append((other_id, other))
                for _candidate_id, candidate in candidates:
                    project_id = candidate.payload.get("project_id")
                    logical_path = candidate.payload.get("logical_path")
                    if (candidate.node_type == "artifact"
                            and isinstance(project_id, str)
                            and isinstance(logical_path, str)):
                        linked_artifacts.append(
                            self.read_api.artifact(project_id, logical_path)
                        )
                if linked_artifacts:
                    detail["linked_artifacts"] = linked_artifacts
                primary_artifact = linked_artifacts[0] if linked_artifacts else None
                from merlin.hud_objects import render_descriptor
                detail["workspace"] = render_descriptor(node, primary_artifact)
                detail["workspace"]["linked_artifacts"] = linked_artifacts
                return self._respond(start_response, "200 OK", detail)
            run_id = environ.get("QUERY_STRING", "")
            selected_run = None
            if run_id.startswith("run_id="):
                from urllib.parse import parse_qs
                values = parse_qs(run_id).get("run_id", [])
                selected_run = values[0] if values else None
            return self._respond(start_response, "200 OK",
                                 self.projector.snapshot(run_id=selected_run))
        except Exception as exc:
            return self._respond(start_response, "503 Service Unavailable",
                                 {"error": "hud_projection_unavailable",
                                  "error_type": type(exc).__name__})

    @staticmethod
    def _respond_html(start_response: Callable[..., Any], body_text: str):
        body = body_text.encode("utf-8")
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("X-Frame-Options", "DENY"),
            ("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"),
        ]
        start_response("200 OK", headers)
        return [body]

    @staticmethod
    def _respond(start_response: Callable[..., Any], status: str,
                 payload: dict[str, Any], *, extra: list[tuple[str, str]] | None = None):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ] + (extra or [])
        start_response(status, headers)
        return [body]


__all__ = ["HudActivityWSGI"]
