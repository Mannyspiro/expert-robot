"""Allowlisted, bundled synthetic fixtures only.

Never reads external seed paths, uploads, production exports or client records.
This controls seed provenance, not whether arbitrary code could write real data.
"""
import json
from importlib.resources import files
from .store import CaseStore
from .workflow import Case, SERVICES

# Independent trusted policy: modifying the fixture alone cannot authorize new
# records. Changes to this policy require code review and new tests.
APPROVED = {
    "workshop_v1": {
        "fixture_id": "wilborn-workshop-v1",
        "data_class": "synthetic",
        "environment": "demo",
        "generator": "hand-authored-fictional-fixture",
        "cases": [
            {"service": "workshop", "count": 3},
            {"service": "document_signing", "count": 2},
            {"service": "insurance_quote", "count": 2},
            {"service": "general", "count": 1},
        ],
    },
}

def load_fixture(name="workshop_v1"):
    if name not in APPROVED:
        raise PermissionError("fixture not allowlisted")
    # No caller-controlled path; bundled resource only.
    resource = files("wilborn_ops.fixtures").joinpath(name + ".json")
    data = json.loads(resource.read_text(encoding="utf-8"))
    if data != APPROVED[name]:
        raise PermissionError("fixture does not match approved policy")
    if set(data) != {"fixture_id", "data_class", "environment", "generator", "cases"}:
        raise ValueError("unexpected fixture fields")
    if data["data_class"] != "synthetic" or data["environment"] != "demo":
        raise PermissionError("non-demo fixture")
    for entry in data["cases"]:
        if (set(entry) != {"service", "count"} or
            entry["service"] not in SERVICES or
            type(entry["count"]) is not int or
            not 0 < entry["count"] <= 20):
            raise ValueError("invalid synthetic fixture entry")
    return data

def seed_demo(store: CaseStore, fixture="workshop_v1"):
    if type(store) is not CaseStore:
        raise TypeError("only the local synthetic CaseStore is supported")
    # Validate fixture before touching the database.
    data = load_fixture(fixture)
    if store.list_cases():
        raise ValueError("seed requires an empty demo database")
    # Atomic seed: no partially populated demo database.
    # CaseStore.save owns its own transaction; use a savepoint-free explicit
    # rollback by preparing records first, then a single transaction below.
    cases = [Case.open(entry["service"])
             for entry in data["cases"] for _ in range(entry["count"])]
    import sqlite3
    try:
        store.db.execute("BEGIN IMMEDIATE")
        if store.db.execute("SELECT 1 FROM cases LIMIT 1").fetchone():
            raise ValueError("seed requires an empty demo database")
        for case in cases:
            store.db.execute(
                """INSERT INTO cases
                (id,service,stage,head,events,data_class,environment,source,verified_real)
                VALUES (?,?,?,?,?,'synthetic','demo',?,0)""",
                (case.id,case.service,case.stage.value,case.head,
                 json.dumps(case.events,sort_keys=True),"wilborn-demo-generated"))
        store.db.execute("COMMIT")
    except BaseException:
        if store.db.in_transaction:
            store.db.execute("ROLLBACK")
        raise
    return {"fixture_id":data["fixture_id"],"data_class":"synthetic",
            "environment":"demo","created":len(cases)}
