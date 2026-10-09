#!/usr/bin/env python3
"""Static upstream Lean import-closure and shared dependency cost report.

Compute from a read-only, SHA-pinned checkout of openai/math/lean.
No Lean claims checked; no modifications to source, permissions or user data.
All missing OAI imports fail closed. Data is an optimization heuristic, not
a formal statement-fidelity or mathematical-correctness certificate.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

COMMIT = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
IMPORT = re.compile(r"^\s*import\s+(.+)$")
MOD = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
MODULE_PREFIXES = ("OAI.", "ComparatorChallenges.")


def profile(upstream, catalog):
    root = upstream / "lean"
    assert root.is_dir(), "missing upstream Lean checkout"
    assert catalog.get("source_commit") == COMMIT
    rows = catalog["declared_results"]
    assert len(rows) == 200 and len({x["declaration"] for x in rows}) == 200
    cache = {}
    failures = []

    def parse_module(module):
        if module in cache:
            return cache[module]
        rel = Path(module.replace(".", "/") + ".lean")
        file = root / rel
        if not file.is_file():
            cache[module] = None
            failures.append({"module": module, "reason": "missing source"})
            return None
        raw = file.read_bytes()
        # UTF-8 should be valid for Lean project sources
        source = raw.decode("utf-8")
        deps = []
        for line in source.splitlines():
            match = IMPORT.match(line)
            if match:
                # Lean accepts multiple imports per line, but comments and
                # nonliteral/dynamic syntaxes require separate checking.
                fields = match.group(1).split("--", 1)[0].split()
                for dep in fields:
                    if not MOD.fullmatch(dep):
                        failures.append({"module": module,
                                         "reason": "unrecognized import syntax",
                                         "import": dep[:100]})
                    elif dep.startswith(MODULE_PREFIXES):
                        deps.append(dep)
        cache[module] = {
            "bytes": len(raw),
            "lines": len(source.splitlines()),
            "sha256": sha256(raw).hexdigest(),
            "imports": sorted(set(deps)),
        }
        return cache[module]

    result = []
    for row in rows:
        mod = row["module_file"][:-5].replace("/", ".")
        pending = [mod]
        seen = set()
        while pending:
            m = pending.pop()
            if m in seen:
                continue
            seen.add(m)
            d = parse_module(m)
            if d is not None:
                pending.extend(d["imports"])
            if len(seen) > 5000:
                raise ValueError("unexpected closure >5000; abort cheap scan")
        files = [x for x in seen if cache.get(x) is not None]
        result.append({
            "declaration": row["declaration"],
            "source_module": mod,
            "comparator_config": row["comparator_config"],
            "local_modules": len(files),
            "local_bytes": sum(cache[m]["bytes"] for m in files),
            "local_lines": sum(cache[m]["lines"] for m in files),
            "unresolved_local_imports": sorted(x for x in seen if cache.get(x) is None),
            # Dependency set is small relative to full source. Store hashes
            # instead of an enormous repeated module-list.
            "closure_digest_sha256": sha256(
                "\n".join(sorted(f"{m}:{cache[m]['sha256']}" for m in files))
                .encode()).hexdigest(),
            "_dependencies": set(files),
        })
    def cost(r):
        return (r["local_modules"], r["local_lines"], r["declaration"])
    # Greedy shared-dependency planning makes each group maximize cache reuse.
    pending = sorted(result, key=cost)
    batches = []
    while pending:
        first = pending.pop(0)
        group = [first]
        union = set(first["_dependencies"])
        while len(group) < 4 and pending:
            partner = min(pending, key=lambda x: (
                len(x["_dependencies"] - union),
                x["local_lines"], x["declaration"]))
            pending.remove(partner)
            group.append(partner)
            union.update(partner["_dependencies"])
        batches.append({
            "batch_index": len(batches),
            "targets": [x["declaration"] for x in group],
            "source_modules": sorted({x["source_module"] for x in group}),
            "shared_local_modules": len(union),
            "shared_local_lines": sum(cache[m]["lines"] for m in union),
            "state": "not_compiled",
        })
    assert sum(len(b["targets"]) for b in batches) == 200
    rankings = sorted(result, key=cost)
    for r in result:
        del r["_dependencies"]
    return {
        "schema_version": 1,
        "experiment": "openai-math-lean-closure-cost-v1",
        "upstream_sha": COMMIT,
        "source_modules_inspected": len(cache),
        "source_modules_present": sum(x is not None for x in cache.values()),
        "unique_files_total_bytes": sum(x["bytes"] for x in cache.values()
                                        if x is not None),
        "results_profiled": len(result),
        "targets_with_missing_imports": sum(bool(x["unresolved_local_imports"])
                                            for x in result),
        "import_resolution_failures": failures[:50],
        "failure_count": len(failures),
        "low_cost_first": [{k:v for k,v in x.items() if k in (
            "declaration", "local_modules", "local_lines", "local_bytes")}
            for x in rankings[:20]],
        "high_cost_last": [{k:v for k,v in x.items() if k in (
            "declaration", "local_modules", "local_lines", "local_bytes")}
            for x in rankings[-10:]],
        "batches": batches,
        "cases": result,
        "kernel_checks_completed": 0,
        "mathematical_truth_claimed": False,
        "user_authority_expanded": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--catalog", type=Path,
                        default=Path("docs/openai-math-catalog-2026-10-09.json"))
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    report = profile(args.upstream, json.loads(args.catalog.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items()
                      if k not in ("cases","batches","low_cost_first","high_cost_last")}))
    if report["failure_count"]:
        raise SystemExit("fail-closed: unresolved local import(s)")


if __name__ == "__main__":
    main()
