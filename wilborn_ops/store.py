"""Local synthetic-data persistence with atomic optimistic concurrency control."""
import json
import sqlite3
from .workflow import Case, Stage

class CaseStore:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS cases
            (id TEXT PRIMARY KEY, service TEXT NOT NULL, stage TEXT NOT NULL,
             head TEXT NOT NULL, events TEXT NOT NULL)""")

    def save(self, case):
        if not case.verify():
            raise ValueError("invalid case history")
        payload = json.dumps(case.events, sort_keys=True)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute(
                "SELECT id,service,stage,head,events FROM cases WHERE id=?",
                (case.id,)).fetchone()
            if row is None:
                self.db.execute("INSERT INTO cases VALUES (?,?,?,?,?)",
                                (case.id, case.service, case.stage.value, case.head, payload))
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
        case = Case(row[0],row[1],Stage(row[2]),json.loads(row[4]),row[3])
        if not case.verify():
            raise ValueError("stored case failed integrity check")
        return case

    def load(self, case_id):
        row = self.db.execute("SELECT id,service,stage,head,events FROM cases WHERE id=?",
                              (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        return self._decode(row)

    def list_cases(self):
        rows = self.db.execute("SELECT id,service,stage,head,events FROM cases ORDER BY rowid").fetchall()
        return [self._decode(row) for row in rows]

    def close(self):
        self.db.close()
