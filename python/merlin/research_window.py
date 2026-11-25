"""Local, durable Merlin research window and explicit event/artifact publisher.

Uses Merlin's canonical registry, graph and outbox. The HTTP surface is read-only.
Only explicitly registered artifact versions can be displayed. No filesystem
browser, model output, verification assertion, or resource sample is invented.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import mimetypes
import os
from pathlib import Path
import sys
from urllib.parse import quote
from wsgiref.simple_server import make_server

from merlin.event_outbox import MerlinEventOutbox
from merlin.hud_runtime import build_hud_runtime
from merlin.knowledge_graph import GraphEdge, GraphNode, MerlinKnowledgeGraph
from merlin.project_registry import MerlinRegistry
from merlin.telemetry import KINDS, normalize_event, telemetry_outbox_sink

PROJECT = "ordered-moments"


class ResearchWindow:
    """Composition around the same canonical stores used for all window actions."""
    def __init__(self, state_dir: str | Path, *, project_id: str = PROJECT, project_title: str | None = None):
        self.state_dir = Path(state_dir)
        self.project_id = project_id
        self.registry = MerlinRegistry(self.state_dir / "registry")
        self.graph = MerlinKnowledgeGraph(self.state_dir / "knowledge.sqlite3")
        self.outbox = MerlinEventOutbox(self.state_dir / "outbox.sqlite3")
        self.registry.register_project(project_id, project_title or "Merlin mathematical research", "3")
        self.project_node = "project:" + project_id
        if self.graph.get_node(self.project_node) is None:
            self.graph.add_node(GraphNode(self.project_node, "project", project_title or "Ordered Moments",
                                         {"project_id": project_id}, "recorded"))
        self.hud = build_hud_runtime(registry=self.registry, graph=self.graph,
                                     outbox=self.outbox, max_events=1000)
        self.topics = tuple("merlin.telemetry." + kind for kind in sorted(KINDS))

    def session(self, run_id: str, question: str | None = None) -> str:
        node_id = "session:" + run_id
        if self.graph.get_node(node_id) is None:
            label = (question or run_id)[:80]
            self.graph.add_node(GraphNode(node_id, "session", label,
                                         {"run_id": run_id}, "recorded"))
            self.graph.add_edge(GraphEdge(self.project_node, "contains", node_id, {}))
        return node_id

    def emit(self, value: dict) -> dict:
        event = normalize_event(value)
        self.session(event["run_id"], event["payload"].get("question"))
        telemetry_outbox_sink(self.outbox)(event)
        return event

    def register_artifact(self, path: str | Path, *, allowed_roots: list[Path],
                          run_id: str, title: str, display_kind: str,
                          caption: str = "", logical_path: str | None = None,
                          evidence_class: str = "unreviewed") -> dict:
        if display_kind not in {"graph", "source", "proof", "data"}:
            raise ValueError("unsupported display kind")
        target = Path(path).resolve(strict=True)
        roots = [root.resolve(strict=True) for root in allowed_roots]
        matching = [root for root in roots if target.is_relative_to(root)]
        if not matching or not target.is_file():
            raise ValueError("artifact must be a regular file inside an explicitly allowed research root")
        owner = max(matching, key=lambda r: len(r.parts))
        logical = logical_path or (owner.name + "/" + target.relative_to(owner).as_posix())
        if target.stat().st_size > 8 * 1024 * 1024:
            raise ValueError("display artifact exceeds 8 MiB")
        media = mimetypes.guess_type(str(target))[0] or "text/plain"
        if target.suffix == ".lean":
            media = "text/x-lean"
        allowed = {"image/png", "image/svg+xml", "image/jpeg", "image/webp",
                   "text/plain", "text/x-lean", "application/json"}
        if media not in allowed or (display_kind == "graph" and not media.startswith("image/")):
            raise ValueError("unsupported media type for this display kind")
        if display_kind != "graph" and media.startswith("image/"):
            raise ValueError("image artifacts must use the graph display kind")
        content = target.read_bytes()
        if len(content) > 8 * 1024 * 1024:
            raise ValueError("display artifact exceeds 8 MiB")
        digest = self.registry.put_artifact(self.project_id, logical, content, media)
        reference = self.registry.artifact_ref(self.project_id, logical)
        # Version is part of identity: reverting bytes creates a new immutable
        # registry version and must not silently reuse an older node's reference.
        identity = json.dumps(reference, sort_keys=True, separators=(",", ":"))
        node_id = "artifact:" + sha256(identity.encode()).hexdigest()
        if self.graph.get_node(node_id) is None:
            self.graph.add_node(GraphNode(node_id, "artifact", title, {
                "project_id": self.project_id, "logical_path": logical,
                "artifact_ref": reference, "display_kind": display_kind,
                "caption": caption, "registered_at": datetime.now(timezone.utc).isoformat(),
            }, evidence_class, "merlin-artifact://" + self.project_id + "/" + quote(logical)))
        session_id = self.session(run_id)
        self.graph.add_edge(GraphEdge(session_id, "uses", node_id, {}))
        event = self.emit({"source": "runtime", "kind": "artifact.registered", "run_id": run_id,
            "payload": {"summary": "Registered " + title, "node_id": node_id,
                        "display_kind": display_kind}, "evidence_refs": ["sha256:" + digest]})
        return {"artifact_ref": reference, "node_id": node_id, "event_id": event["event_id"],
                "url": "/api/hud/artifact?node_id=" + quote(node_id)}

    def application(self, environ, start_response):
        if environ.get("PATH_INFO") == "/":
            start_response("302 Found", [("Location", "/dashboard"), ("Content-Length", "0")])
            return [b""]
        # Restoration is a read-only projection. It never leases or acknowledges.
        records = self.outbox.recent(topics=self.topics, limit=1000)
        self.hud.projector.ingest_many(record["payload"] for record in records)
        return self.hud.application(environ, start_response)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--project-id", default=PROJECT)
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Open the observable Merlin program window")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5173")))
    serve.add_argument("--no-open", action="store_true", help="Leave browser opening to the caller")
    serve.add_argument("--strictPort", action="store_true", help="Require the selected port (already the default)")
    emit = sub.add_parser("emit", help="Publish one actual, source-labelled event from JSON stdin")
    emit.add_argument("--event-file", type=Path)
    artifact = sub.add_parser("artifact", help="Register and display an exact research artifact")
    artifact.add_argument("--path", type=Path, required=True)
    artifact.add_argument("--allow-root", action="append", type=Path, required=True)
    artifact.add_argument("--run-id", required=True)
    artifact.add_argument("--title", required=True)
    artifact.add_argument("--caption", default="")
    artifact.add_argument("--display-kind", choices=["graph", "source", "proof", "data"], required=True)
    artifact.add_argument("--logical-path")
    artifact.add_argument("--evidence-class", default="unreviewed")
    args = parser.parse_args(argv)
    window = ResearchWindow(args.state_dir, project_id=args.project_id)
    if args.command == "emit":
        raw = args.event_file.read_text() if args.event_file else sys.stdin.read()
        event = window.emit(json.loads(raw))
        print(json.dumps({"event_id": event["event_id"], "kind": event["kind"], "run_id": event["run_id"]}))
    elif args.command == "artifact":
        result = window.register_artifact(args.path, allowed_roots=args.allow_root,
            run_id=args.run_id, title=args.title, display_kind=args.display_kind,
            caption=args.caption, logical_path=args.logical_path, evidence_class=args.evidence_class)
        print(json.dumps(result, indent=2))
    else:
        if not 1 <= args.port <= 65535:
            raise ValueError("invalid port")
        with make_server(args.host, args.port, window.application) as server:
            url = "http://127.0.0.1:" + str(server.server_port) + "/dashboard"
            print(json.dumps({"window": url, "state_dir": str(args.state_dir),
                              "read_only_http": True}), flush=True)
            if not args.no_open:
                import webbrowser
                webbrowser.open(url)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
