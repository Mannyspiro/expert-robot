"""Deterministic theorem dependency DAG extracted from Merlin's Lean registry.

The registry's explicit uses relation is authoritative for graph edges.
Lean declaration headers are hashed as surface syntax, not kernel-normalized
statements; a Lean elaborator/receipt remains necessary for formal identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _top_level_colon(header: str) -> int | None:
    depth = 0
    for index, char in enumerate(header):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == ":" and depth == 0:
            return index
    return None


def _declaration_header(source: str, local_name: str) -> dict[str, str] | None:
    pattern = re.compile(
        r"(?m)^\s*(?:(?:private|protected)\s+)?theorem\s+"
        + re.escape(local_name) + r"\b"
    )
    match = pattern.search(source)
    if not match:
        return None
    end = source.find(":=", match.end())
    if end < 0:
        return None
    header = source[match.start():end].strip()
    colon = _top_level_colon(header)
    if colon is None:
        return None
    binders = header[:colon].strip()
    proposition = header[colon + 1:].strip()
    if not binders or not proposition:
        return None
    return {
        "header": header,
        "binders": binders,
        "proposition": proposition,
        "surface_statement_sha256": sha256_text(proposition),
        "surface_binders_sha256": sha256_text(binders),
        "surface_declaration_sha256": sha256_text(header),
    }


def extract_theorem_dag(
    registry_path: str | Path,
    formal_root: str | Path | None = None,
    *,
    require_surface_parse: bool = False,
) -> dict[str, Any]:
    registry_file = Path(registry_path)
    formal_dir = Path(formal_root) if formal_root is not None else registry_file.parent
    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    if registry.get("schema_version") != 1 or not isinstance(registry.get("theorems"), list):
        raise ValueError("unsupported theorem registry schema")
    entries = registry["theorems"]
    names = [item.get("name") for item in entries]
    if any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError("every theorem must have a non-empty name")
    if len(names) != len(set(names)):
        raise ValueError("duplicate theorem names in registry")
    known = set(names)
    nodes, edges = [], []
    for item in sorted(entries, key=lambda row: row["name"]):
        name = item["name"]
        source_rel = item.get("source", "")
        source_path = formal_dir / source_rel
        if not source_rel or not source_path.is_file():
            raise FileNotFoundError(f"missing Lean source for {name}: {source_path}")
        source_text = source_path.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        declaration = _declaration_header(source_text, name.rsplit(".", 1)[-1])
        dependencies = item.get("uses", [])
        if not isinstance(dependencies, list) or any(dep not in known for dep in dependencies):
            missing = sorted(set(dependencies) - known) if isinstance(dependencies, list) else []
            raise ValueError(f"invalid theorem dependencies for {name}: {missing}")
        for dependency in sorted(set(dependencies)):
            edges.append({"theorem": name, "depends_on": dependency})
        nodes.append({
            "id": name,
            "source": source_rel,
            "source_sha256": source_hash,
            "domain": str(item.get("domain", "unspecified")),
            "status": str(item.get("status", "unclassified")),
            "tags": sorted(str(tag) for tag in item.get("tags", [])),
            "dependencies": sorted(set(dependencies)),
            "registry_statement_sha256": sha256_text(str(item.get("statement", ""))),
            "lean_surface_declaration": declaration,
            "lean_surface_parse_status": "parsed" if declaration else "unparsed",
            "formal_qualification_required": True,
        })
    unparsed = [node["id"] for node in nodes if node["lean_surface_parse_status"] != "parsed"]
    if require_surface_parse and unparsed:
        raise ValueError("unparsed registered Lean declarations: " + ", ".join(unparsed))
    dependencies = {node["id"]: set(node["dependencies"]) for node in nodes}
    ready = sorted(name for name, deps in dependencies.items() if not deps)
    topological_order = []
    while ready:
        current = ready.pop(0)
        topological_order.append(current)
        for name in sorted(dependencies):
            if current in dependencies[name]:
                dependencies[name].remove(current)
                if not dependencies[name] and name not in topological_order and name not in ready:
                    ready.append(name)
        ready.sort()
    if len(topological_order) != len(nodes):
        cyclic = sorted(name for name, deps in dependencies.items() if deps)
        raise ValueError("theorem dependency cycle detected: " + ", ".join(cyclic))
    payload = {
        "schema": "merlin-theorem-dependency-dag-v1",
        "registry_sha256": hashlib.sha256(registry_file.read_bytes()).hexdigest(),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": sorted(edges, key=lambda edge: (edge["theorem"], edge["depends_on"])),
        "topological_order_dependencies_first": topological_order,
        "surface_hash_semantics": "textual Lean declaration header only; not elaborated/kernel-normalized identity",
    }
    payload["dag_sha256"] = sha256_text(canonical_json(payload))
    return payload


def write_theorem_dag(registry_path: str | Path, output_path: str | Path,
                      formal_root: str | Path | None = None,
                      *, require_surface_parse: bool = False) -> dict[str, Any]:
    dag = extract_theorem_dag(registry_path, formal_root,
                               require_surface_parse=require_surface_parse)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical_json(dag) + "\n", encoding="utf-8")
    return dag


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Merlin's Lean theorem dependency DAG")
    parser.add_argument("--registry", default="formal/theorem_registry.json")
    parser.add_argument("--formal-root", default="formal")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = write_theorem_dag(args.registry, args.output, args.formal_root,
                               require_surface_parse=True)
    print(json.dumps({
        "dag_sha256": result["dag_sha256"],
        "node_count": result["node_count"],
        "edge_count": result["edge_count"],
        "unparsed_surface_declarations": sum(
            node["lean_surface_parse_status"] != "parsed" for node in result["nodes"]
        ),
    }, sort_keys=True))
