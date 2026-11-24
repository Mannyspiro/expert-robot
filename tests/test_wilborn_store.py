import tempfile
import unittest
from pathlib import Path
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case, Stage

class StoreTests(unittest.TestCase):
    def test_persist_reload_and_reject_divergence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"cases.db"
            db=CaseStore(path)
            case=Case.open("workshop")
            db.save(case)
            original=db.load(case.id)
            case.move(Stage.SCHEDULED,"staff")
            db.save(case)
            self.assertEqual(db.load(case.id).stage,Stage.SCHEDULED)
            original.move(Stage.SCHEDULED,"another")
            with self.assertRaises(ValueError):
                db.save(original)
            db.close()
            reopened=CaseStore(path)
            self.assertEqual(len(reopened.list_cases()),1)
            reopened.close()

    def test_tampered_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            db=CaseStore(Path(folder)/"cases.db")
            case=Case.open("general")
            db.save(case)
            db.db.execute("UPDATE cases SET stage='closed' WHERE id=?",(case.id,))
            db.db.commit()
            with self.assertRaises(ValueError):
                db.load(case.id)
            db.close()
