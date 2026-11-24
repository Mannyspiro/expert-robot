"""Synthetic-only SQLite store with immutable database-enforced provenance.

This demo store refuses legacy/unclassified schemas rather than guessing provenance.
Not suitable for real client records.
"""
import json
import sqlite3
from .workflow import Case, Stage
from .provenance import DataClass, Provenance, assert_demo

DEMO_SOURCE = "wilborn-demo-generated"

class CaseStore:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            self.db.execute("PRAGMA busy_timeout=5000")
            self.db.execute("""CREATE TABLE IF NOT EXISTS cases
                (id TEXT PRIMARY KEY, service TEXT NOT NULL, stage TEXT NOT NULL,
                 head TEXT NOT NULL, events TEXT NOT NULL,
                 data_class TEXT NOT NULL DEFAULT 'synthetic'
                   CHECK(data_class = 'synthetic'),
                 environment TEXT NOT NULL DEFAULT 'demo'
                   CHECK(environment = 'demo'),
                 source TEXT NOT NULL DEFAULT 'wilborn-demo-generated'
                   CHECK(source = 'wilborn-demo-generated'),
                 verified_real INTEGER NOT NULL DEFAULT 0
                   CHECK(verified_real = 0))""")
            cols = {row[1] for row in self.db.execute("PRAGMA table_info(cases)")}
            required = {"id","service","stage","head","events","data_class",
                        "environment","source","verified_real"}
            if not required.issubset(cols):
                raise ValueError("legacy/unclassified schema rejected; do not auto-migrate")
            self.db.execute("""CREATE TRIGGER IF NOT EXISTS cases_no_reclassify
                BEFORE UPDATE OF data_class,environment,source,verified_real ON cases
                BEGIN SELECT RAISE(ABORT,'provenance immutable'); END""")
        except BaseException:
            self.db.close()
            raise

    @property
    def provenance(self):
        return Provenance(DataClass.SYNTHETIC, "demo", DEMO_SOURCE)

    def save(self, case):
        assert_demo(self.provenance)
        if not case.verify():
            raise ValueError("invalid case history")
        payload = json.dumps(case.events, sort_keys=True)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT id,service,stage,head,events,data_class,environment,source,verified_real FROM cases WHERE id=?",
                (case.id,)).fetchone()
            if row is None:
                self.db.execute("""INSERT INTO cases
                    (id,service,stage,head,events,data_class,environment,source,verified_real)
                    VALUES (?,?,?,?,?,'synthetic','demo',?,0)""",
                    (case.id,case.service,case.stage.value,case.head,payload,DEMO_SOURCE))
            else:
                previous = self._decode(row)
                if (case.service != previous.service or
                    len(case.events) <= len(previous.events) or
                    case.events[:len(previous.events)] != previous.events):
                    raise ValueError("stale, duplicate or divergent history")
                cursor = self.db.execute(
                    "UPDATE cases SET stage=?,head=?,events=? WHERE id=? AND head=?",
                    (case.stage.value,case.head,payload,case.id,previous.head))
                if cursor.rowcount != 1:
                    raise ValueError("concurrent update conflict")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    @staticmethod
    def _decode(row):
        if len(row) != 9 or row[5:] != ("synthetic","demo",DEMO_SOURCE,0):
            raise ValueError("record provenance rejected")
        case = Case(row[0],row[1],Stage(row[2]),json.loads(row[4]),row[3])
        if not case.verify():
            raise ValueError("stored case failed integrity check")
        return case

    def load(self, case_id):
        row = self.db.execute("""SELECT id,service,stage,head,events,
            data_class,environment,source,verified_real FROM cases WHERE id=?""",
            (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        return self._decode(row)

    def list_cases(self):
        rows = self.db.execute("""SELECT id,service,stage,head,events,
            data_class,environment,source,verified_real FROM cases ORDER BY rowid""").fetchall()
        return [self._decode(row) for row in rows]

    def close(self):
        self.db.close()
