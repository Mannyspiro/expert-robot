"""Multiscale graph projection over recorded telemetry identifiers."""
from __future__ import annotations
from typing import Any

def build_telemetry_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: set[tuple[str, str, str]] = set()
    for event in events:
        run_id = str(event.get("run_id", ""))
        event_id = str(event.get("event_id", ""))
        if not run_id or not event_id:
            continue
        run_node = "run:" + run_id
        nodes.setdefault(run_node, {"id": run_node, "kind": "run", "label": run_id})
        task_id = event.get("task_id")
        parent = run_node
        if isinstance(task_id, str) and task_id:
            task_node = "task:" + run_id + ":" + task_id
            nodes.setdefault(task_node, {"id": task_node, "kind": "task", "label": task_id})
            edges.add((run_node, task_node, "contains"))
            parent = task_node
        event_node = "event:" + event_id
        nodes[event_node] = {"id": event_node, "kind": "event",
            "label": event.get("kind", "event"), "source": event.get("source"),
            "timestamp": event.get("timestamp")}
        edges.add((parent, event_node, "observed"))
        for index, ref in enumerate(event.get("evidence_refs", [])):
            evidence_node = "evidence:" + str(ref)
            nodes.setdefault(evidence_node, {"id": evidence_node, "kind": "evidence",
                                              "label": str(ref)[:48]})
            edges.add((event_node, evidence_node, "references"))
    return {"schema": "merlin-multiscale-graph/1",
            "levels": ["run", "task", "event", "evidence"],
            "nodes": list(nodes.values()),
            "edges": [{"source": a, "target": b, "kind": kind}
                      for a, b, kind in sorted(edges)],
            "source_separation_preserved": True,
            "promotion_authorized": False}
