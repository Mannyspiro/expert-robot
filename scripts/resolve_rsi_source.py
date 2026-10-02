#!/usr/bin/env python3
"""Bind collar artifacts to an immutable source before candidate checkout.

Push runs identify candidate source with their head SHA. A manually dispatched
collar may run its trusted workflow on main and evaluate a different candidate;
manual qualification therefore binds the artifact SHA to the requested branch.
"""

import argparse
import json
import re
from pathlib import Path


def resolve_source(evidence, run, *, repository, candidate_ref, source_run_id,
                   event_name, event_source_sha="", resolved_candidate_sha=""):
    if not re.fullmatch(r"candidate/[A-Za-z0-9._/-]+", candidate_ref):
        raise ValueError("candidate ref must be a candidate/ branch")
    if type(run.get("id")) is not int or run["id"] != source_run_id:
        raise ValueError("collar workflow run id mismatch")
    if type(evidence.get("source_run_id")) is not int or evidence["source_run_id"] != source_run_id:
        raise ValueError("collar artifact source_run_id mismatch")
    if run.get("path", "").split("@", 1)[0] != ".github/workflows/collared-rsi-generation.yml":
        raise ValueError("evidence run is not the trusted collar workflow")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("collar workflow run did not complete successfully")
    if run.get("head_repository", {}).get("full_name") != repository:
        raise ValueError("collar workflow source repository mismatch")
    source_sha = evidence.get("candidate_sha", "")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("collar artifact has an invalid candidate SHA")
    if run.get("event") not in {"push", "workflow_dispatch"}:
        raise ValueError("unsupported collar workflow event")
    if run["event"] == "push":
        if source_sha != run.get("head_sha") or candidate_ref != run.get("head_branch"):
            raise ValueError("push collar artifact does not match its source commit/ref")

    if event_name == "workflow_run":
        if source_sha != event_source_sha or event_source_sha != run.get("head_sha"):
            raise ValueError("collar artifact does not match the triggering source SHA")
        if candidate_ref != run.get("head_branch"):
            raise ValueError("collar source branch does not match triggering candidate ref")
    elif event_name == "workflow_dispatch":
        if source_sha != resolved_candidate_sha:
            raise ValueError("candidate ref moved or does not match collar artifact SHA")
    else:
        raise ValueError("unsupported qualification event")

    return {"schema_version": 1, "candidate_sha": source_sha,
            "candidate_ref": candidate_ref, "source_run_id": source_run_id,
            "source_event": run["event"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--workflow-run", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-source-sha", default="")
    parser.add_argument("--resolved-candidate-sha", default="")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    if args.source_run_id < 1:
        parser.error("--source-run-id must be positive")
    try:
        result = resolve_source(
            json.loads(args.evidence.read_text(encoding="utf-8")),
            json.loads(args.workflow_run.read_text(encoding="utf-8")),
            repository=args.repository, candidate_ref=args.candidate_ref,
            source_run_id=args.source_run_id, event_name=args.event_name,
            event_source_sha=args.event_source_sha,
            resolved_candidate_sha=args.resolved_candidate_sha)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.github_output:
        with args.github_output.open("a", encoding="utf-8") as output:
            output.write(f"candidate_sha={result['candidate_sha']}\n")


if __name__ == "__main__":
    main()
