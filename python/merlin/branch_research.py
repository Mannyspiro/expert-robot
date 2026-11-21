"""Bounded durable research DAG with exact checkpoint and outcome identity."""
from contextlib import closing
from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Branch:
    id: str
    title: str
    priority: int
    prerequisites: tuple[str, ...] = ()
    exploratory: bool = False


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def branch_catalogue(branches):
    catalogue = {branch.id: branch for branch in branches}
    if not 1 <= len(branches) == len(catalogue) <= 32 or any(
        not node.id or not node.title or len(set(node.prerequisites)) != len(node.prerequisites)
        or set(node.prerequisites) - catalogue.keys()
        for node in branches
    ):
        raise ValueError("Invalid bounded branch catalogue.")
    closed = set()
    while (ready := {node.id for node in branches if set(node.prerequisites) <= closed} - closed):
        closed.update(ready)
    if len(closed) != len(branches):
        raise ValueError("Branch prerequisites contain a cycle.")
    return catalogue


def choose_branch(branches, results):
    ready = [branch for key, branch in branches.items() if key not in results
             and all(results.get(parent, {}).get("status") == "verified" for parent in branch.prerequisites)]
    if not ready:
        return None
    reserved = (len(results) + 1) % 3 == 0
    eligible = [node for node in ready if node.exploratory] if reserved else []
    return min(eligible or ready, key=lambda branch: (-branch.priority, branch.id))


class BranchResearch:
    def __init__(self, database, branches):
        self.database = Path(database)
        self.branches = branch_catalogue(branches)
        self.plan_sha256 = digest([asdict(branch) for branch in branches])

    def _rows(self, db):
        previous = None
        results = {}
        for branch, body, checksum in db.execute("SELECT branch,body,sha FROM branch_receipts ORDER BY stage"):
            receipt = json.loads(body)
            node = self.branches.get(branch)
            if node is None or any(parent not in results or results[parent]["status"] != "verified"
                                   for parent in node.prerequisites):
                raise RuntimeError("Research receipt has unmet prerequisites.")
            inputs = {parent: results[parent]["receipt_sha256"] for parent in node.prerequisites}
            if (receipt.get("prerequisite_receipts") != inputs
                    or digest(receipt.get("evidence")) != receipt.get("evidence_sha256")
                    or digest(receipt) != checksum or receipt["parent_sha256"] != previous
                    or receipt["branch"] != branch or receipt["plan_sha256"] != self.plan_sha256):
                raise RuntimeError("Research receipt chain or plan identity differs.")
            results[branch] = {**receipt, "receipt_sha256": checksum}
            previous = checksum
        return results

    def _choose(self, results):
        return choose_branch(self.branches, results)

    def step(self, evaluate, *, budget=1):
        """Commit at most four completed evaluations, one transaction per branch."""
        if type(budget) is not int or not 1 <= budget <= 4:
            raise ValueError("Branch budget must be from one to four.")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database, timeout=15)) as db:
            db.execute("CREATE TABLE IF NOT EXISTS branch_receipts "
                       "(stage INTEGER PRIMARY KEY, branch TEXT UNIQUE NOT NULL, body TEXT NOT NULL, sha TEXT NOT NULL)")
            for _ in range(budget):
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    results = self._rows(db)
                    branch = self._choose(results)
                    if branch is None:
                        break
                    # Lineage is scheduler-owned. Give the evaluator a detached
                    # snapshot so even nested mutations cannot alter the checkpoint.
                    inputs = {key: results[key] for key in branch.prerequisites}
                    prerequisite_receipts = {key: row["receipt_sha256"] for key, row in inputs.items()}
                    parent_sha256 = next(reversed(results.values()))["receipt_sha256"] if results else None
                    evidence = evaluate(branch.id, deepcopy(inputs))
                    if (not isinstance(evidence, dict) or type(evidence.get("passed")) is not bool
                            or not isinstance(evidence.get("detail"), str)):
                        raise ValueError("A branch must return a measured pass or failure and detail.")
                    receipt = {
                        "plan_sha256": self.plan_sha256,
                        "parent_sha256": parent_sha256,
                        "branch": branch.id, "status": "verified" if evidence["passed"] else "failed",
                        "evidence": evidence, "evidence_sha256": digest(evidence),
                        "prerequisite_receipts": prerequisite_receipts,
                    }
                    body = canonical(receipt)
                    if len(body.encode()) > 64 * 1024:
                        raise ValueError("Branch evidence exceeds the recorded budget.")
                    db.execute("INSERT INTO branch_receipts VALUES (?, ?, ?, ?)",
                               (len(results) + 1, branch.id, body, digest(receipt)))
        return self.status()

    def status(self):
        results = {}
        if self.database.is_file():
            with closing(sqlite3.connect(self.database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='branch_receipts'").fetchone():
                    results = self._rows(db)
        quests = []
        for branch in self.branches.values():
            row = results.get(branch.id)
            waiting = [key for key in branch.prerequisites if results.get(key, {}).get("status") != "verified"]
            quests.append({"id": branch.id, "title": branch.title,
                           "status": row["status"] if row else "waiting" if waiting else "ready",
                           "detail": row["evidence"]["detail"] if row else
                           "Requires " + ", ".join(waiting) if waiting else "Ready for a verified experiment."})
        verified = sum(item["status"] == "verified" for item in quests)
        upcoming = self._choose(results)
        return {
            "schema": "merlin-branch-research/1", "plan_sha256": self.plan_sha256,
            "summary": f"Branch research has verified {verified} of {len(quests)} quests.",
            "scope": "Local checkable research quests. Experience points count accepted evidence, not intelligence or training.",
            "progression": {"xp": 10 * verified, "completed": verified, "total": len(quests)},
            "checkpoint": {"cursor": len(results), "total": len(quests)},
            "selected": upcoming.title if upcoming else None, "quests": quests, "receipts": list(results.values()),
        }
