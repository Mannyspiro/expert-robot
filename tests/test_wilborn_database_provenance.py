import sqlite3
import tempfile
import unittest
from pathlib import Path
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case
from wilborn_ops.gateway import BusinessGateway,Identity

class DatabaseProvenanceTests(unittest.TestCase):
    def test_database_rejects_relabel_and_real_insert(self):
        with tempfile.TemporaryDirectory() as folder:
            db=CaseStore(Path(folder)/"demo.db")
            case=Case.open("workshop")
            db.save(case)
            with self.assertRaises(sqlite3.IntegrityError):
                db.db.execute("UPDATE cases SET data_class='real' WHERE id=?",(case.id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.db.execute("UPDATE cases SET source='other' WHERE id=?",(case.id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.db.execute("""INSERT INTO cases
                    (id,service,stage,head,events,data_class,environment,source,verified_real)
                    VALUES ('fake','general','intake','0','[]','real','production','import',1)""")
            self.assertEqual(db.load(case.id).id,case.id)
            db.close()

    def test_legacy_unclassified_schema_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"old.db"
            conn=sqlite3.connect(path)
            conn.execute("""CREATE TABLE cases
                (id TEXT PRIMARY KEY,service TEXT,stage TEXT,head TEXT,events TEXT)""")
            conn.close()
            with self.assertRaises(ValueError):
                CaseStore(path)

    def test_gateway_refuses_untrusted_store_provenance(self):
        class FakeStore:
            provenance=None
        with self.assertRaises(PermissionError):
            BusinessGateway(FakeStore())
