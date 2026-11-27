"""Register and dispatch the Merlin production crew through OpenBot's local API."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import build_opener, ProxyHandler, Request


HERE = Path(__file__).resolve().parent
OPENER = build_opener(ProxyHandler({}))


def request(base, route, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    with OPENER.open(Request(base + route, data, headers), timeout=timeout) as response:
        return json.load(response)


def ensure_crew(base, workspace, jobs):
    bots = request(base, "/api/bots")["bots"]
    crew = {}
    for job in jobs:
        workspace_id = hashlib.sha256(workspace.encode()).hexdigest()[:8]
        name = "Merlin Studio " + workspace_id + " / " + job["id"]
        matches = [bot for bot in bots if bot["name"] == name and bot["workspace"] == workspace]
        if len(matches) > 1:
            raise ValueError(f"Duplicate OpenBot crew profile: {name}")
        fields = {key: job[key] for key in ("role", "instructions")}
        if matches and any(matches[0].get(key) != value for key, value in fields.items()):
            raise ValueError(f"OpenBot profile has different instructions: {name}")
        crew[job["id"]] = matches[0] if matches else request(
            base, "/api/bots", dict(fields, name=name, workspace=workspace)
        )["bot"]
    return crew


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:4178")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--job")
    parser.add_argument("--task")
    parser.add_argument("--receipts", type=Path, help="JSON object mapping reviewed job IDs to receipt paths")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    url = urlsplit(base)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "::1"} or url.path
            or url.query or url.fragment or url.username is not None):
        parser.error("Use an OpenBot daemon on a numeric loopback HTTP address")
    workspace = args.workspace.resolve(strict=True)
    if not workspace.is_dir():
        parser.error("The workspace must be a directory")
    jobs = json.loads((HERE / "crew.json").read_text())["jobs"]
    if bool(args.job) != bool(args.task):
        parser.error("Supply both --job and --task to dispatch a job")
    if not args.job:
        crew = ensure_crew(base, str(workspace), jobs)
        print(json.dumps({key: bot["id"] for key, bot in crew.items()}, indent=2))
        return
    receipts = json.loads(args.receipts.read_text()) if args.receipts else {}
    chosen = next((job for job in jobs if job["id"] == args.job), None)
    if chosen is None:
        parser.error(f"Unknown job {args.job}")
    inputs = []
    for dependency in chosen["requires"]:
        if dependency not in receipts:
            parser.error(f"Missing reviewed receipt for {dependency}")
        receipt = (workspace / receipts[dependency]).resolve()
        if not receipt.is_relative_to(workspace) or not receipt.is_file():
            parser.error(f"Receipt for {dependency} must be inside the workspace")
        evidence = json.loads(receipt.read_text())
        if evidence.get("job") != dependency or evidence.get("approved") is not True:
            parser.error(f"Receipt for {dependency} must identify an approved job")
        inputs.append(f"{dependency}: {receipt.relative_to(workspace)}")
    crew = ensure_crew(base, str(workspace), jobs)
    message = args.task
    if inputs:
        message += "\nReviewed upstream receipts in this workspace:\n" + "\n".join(inputs)
    bot_id = quote(crew[args.job]["id"], safe="")
    print(json.dumps(request(base, f"/api/bots/{bot_id}/chat", {"message": message, "maxTurns": 1}, timeout=180), indent=2))


if __name__ == "__main__":
    main()
