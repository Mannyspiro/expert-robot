"""Local prototype persistence. Synthetic/non-sensitive data ONLY."""
import json
import sqlite3
from pathlib import Path
from .workflow import Case, Stage

class CaseStore:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("""CREATE TABLE IF NOT EXISTS cases
            (id TEXT PRIMARY KEY, service TEXT NOT NULL, stage TEXT NOT NULL,
             head TEXT NOT NULL, events TEXT NOT NULL)""")
        self.db.commit()

    def save(self, case):
        if not case.verify():
            raise ValueError("invalid case history")
        payload=json.dumps(case.events,sort_keys=True)
        with self.db:
            old=self.db.execute("SELECT head FROM cases WHERE id=?",(case.id,)).fetchone()
            if old is None:
                if case.events and case.events[0]["prev"]!="0"*64:
                    raise ValueError("invalid origin")
                self.db.execute("INSERT INTO cases VALUES (?,?,?,?,?)",
                                (case.id,case.service,case.stage.value,case.head,payload))
            else:
                # Prevent stale writers from overwriting more recent transitions.
                previous=self.load(case.id)
                if len(case.events)<len(previous.events) or case.events[:len(previous.events)]!=previous.events:
                    raise ValueError("stale or divergent history")
                self.db.execute("UPDATE cases SET service=?,stage=?,head=?,events=? WHERE id=? AND head=?",
                                (case.service,case.stage.value,case.head,payload,case.id,old[0]))

    def load(self, case_id):
        row=self.db.execute("SELECT id,service,stage,head,events FROM cases WHERE id=?",
                            (case_id,)).fetchone()
        if row is None: raise KeyError(case_id)
        case=Case(row[0],row[1],Stage(row[2]),json.loads(row[4]),row[3])
        if not case.verify(): raise ValueError("stored case failed integrity check")
        return case

    def list_cases(self):
        rows=self.db.execute("SELECT id FROM cases ORDER BY rowid").fetchall()
        return [self.load(row[0]) for row in rows]

    def close(self):
        self.db.close()
