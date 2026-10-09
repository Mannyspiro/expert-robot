#!/usr/bin/env python3
"""Low-compute source/comparator triage for ALL 200 upstream Lean declarations.

Only downloads pinned source text and comparator configurations. It DOES NOT
invoke the Lean kernel, verify proof arguments, run downloaded code or alter
qualification/production state. Failures are retained rather than waved away.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/openai-math-catalog-2026-10-09.json"
HEAD = "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb"
BASE = "https://raw.githubusercontent.com/openai/math/" + HEAD + "/lean/"
PATH = re.compile(r"^(?:OAI|ComparatorChallenges)/[a-zA-Z0-9_./-]+\.(?:lean|json)$")
SAFE_AX = {"propext", "Classical.choice", "Quot.sound"}


def download(path):
    if not PATH.fullmatch(path) or ".." in path or path.startswith("/"):
        raise ValueError("untrusted upstream path")
    url = BASE + path
    # No credentials or secrets, no target scanning; only pinned GitHub source.
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "expert-robot-openai-proof-triage/1",
                              "Accept": "text/plain"})
            with urllib.request.urlopen(request, timeout=12) as response:
                if not response.geturl().startswith(BASE):
                    raise ValueError("unexpected URL redirect")
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("source too large for cheap scan")
            text = data.decode("utf-8")
            blobsha = hashlib.sha1(
                ("blob " + str(len(data)) + "\0").encode() + data
            ).hexdigest()
            return {"ok": True, "git_blob_sha1": blobsha, "bytes": len(data),
                    "text": text}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                return {"ok": False, "error": type(e).__name__}
            time.sleep(0.5 * (attempt + 1))
        except (UnicodeError, ValueError) as e:
            return {"ok": False, "error": type(e).__name__}
    return {"ok": False, "error": "unresolved"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--workers", type=int, default=6)
    args = p.parse_args()
    if not 1 <= args.workers <= 8:
        raise ValueError("bounded network concurrency 1..8")
    registry = json.loads(CATALOG.read_text(encoding="utf-8"))
    if (registry["source_commit"] != HEAD or registry["declaration_count"] != 200):
        raise ValueError("upstream source pin or count changed")
    decls = registry["declared_results"]
    paths = sorted({"lean/" + d["module_file"] for d in decls} |
                   {"lean/" + d["comparator_config"] for d in decls})
    # Strip the local root but preserve explicit whitelist for downloaded paths.
    files = [s[5:] for s in paths]
    scans = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future = {pool.submit(download, path): path for path in files}
        for f in concurrent.futures.as_completed(future):
            scans[future[f]] = f.result()
    cases = []
    for d in decls:
        mod = scans[d["module_file"]]
        cfg = scans[d["comparator_config"]]
        row = {"declaration": d["declaration"],
               "module_file": d["module_file"],
               "comparator_config": d["comparator_config"],
               "source_download_ok": mod["ok"],
               "comparator_download_ok": cfg["ok"],
               "declared_identifier_visible": False,
               "config_names_declaration": False,
               "axiom_allowlist_subset": False,
               "static_review_only": True,
               "kernel_rechecked": False}
        if mod["ok"]:
            name = d["declaration"].rsplit(".", 1)[-1]
            row["declared_identifier_visible"] = bool(
                re.search(r"\b" + re.escape(name) + r"\b", mod["text"]))
            row["module_blob_sha1"] = mod["git_blob_sha1"]
            row["module_bytes"] = mod["bytes"]
            # These are merely *suspicion indicators*, not a sound source audit.
            row["source_has_proof_escape_token"] = bool(
                re.search(r"\b(sorry|admit|native_decide)\b", mod["text"]))
        else:
            row["source_failure"] = mod["error"]
        if cfg["ok"]:
            row["comparator_blob_sha1"] = cfg["git_blob_sha1"]
            try:
                parsed = json.loads(cfg["text"])
                row["config_names_declaration"] = (
                    d["declaration"] in parsed.get("theorem_names", []))
                row["axiom_allowlist_subset"] = (
                    set(parsed.get("permitted_axioms", [])) <= SAFE_AX)
                row["config_solution_module"] = parsed.get("solution_module")
                row["config_solution_module_matches"] = (
                    parsed.get("solution_module") ==
                    d["module_file"][:-5].replace("/", "."))
            except (ValueError, TypeError):
                row["config_parse_failure"] = True
        else:
            row["comparator_failure"] = cfg["error"]
        cases.append(row)
    result = {
        "experiment": "openai-math-upstream-source-screen-v1",
        "source_commit": HEAD,
        "total_declarations": len(cases),
        "unique_source_and_config_paths": len(files),
        "files_retrieved": sum(v["ok"] for v in scans.values()),
        "failed_file_paths": sorted(k for k,v in scans.items() if not v["ok"]),
        "declarations_with_visible_identifier":
            sum(v["declared_identifier_visible"] for v in cases),
        "declarations_with_config_name":
            sum(v["config_names_declaration"] for v in cases),
        "declarations_with_matching_solution_module":
            sum(v.get("config_solution_module_matches", False) for v in cases),
        "declarations_with_restricted_axiom_allowlist":
            sum(v["axiom_allowlist_subset"] for v in cases),
        "possible_source_escape_tokens":
            sum(v.get("source_has_proof_escape_token", False) for v in cases),
        "solution_module_mapping_differences": [
            {"declaration": x["declaration"],
             "source_module": x["module_file"][:-5].replace("/", "."),
             "comparator_solution_module": x.get("config_solution_module")}
            for x in cases
            if x["comparator_download_ok"] and
            not x.get("config_solution_module_matches", False)
        ],
        "failed_declarations": [
            x["declaration"] for x in cases
            if not all((x["source_download_ok"], x["comparator_download_ok"],
                        x["declared_identifier_visible"],
                        x["config_names_declaration"],
                        x["axiom_allowlist_subset"])))
        ],
        "cases": cases,
        "bytes_downloaded": sum(x.get("bytes",0) for x in scans.values()),
        "lean_builds_executed": 0,
        "mathematical_arguments_verified": 0,
        "full_paper_review_performed": False,
        "network_scope": "pinned raw.githubusercontent.com/openai/math/Lean source and configs only",
        "promotion_or_production_authority": False,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ("cases", "failed_declarations")}))
    print(json.dumps({"mapping_differences":
                      result["solution_module_mapping_differences"]}))
    # Incomplete screening must NOT become a green proof-qualification gate.
    if result["failed_file_paths"] or result["failed_declarations"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
