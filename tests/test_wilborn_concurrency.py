import tempfile
import unittest
from pathlib import Path
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case, Stage

class StoreConcurrencyTests(unittest.TestCase):
    def test_conflicting_writers_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"cases.db"
            a=CaseStore(path)
            b=CaseStore(path)
            case=Case.open("workshop")
            a.save(case)
            first=a.load(case.id)
            second=b.load(case.id)
            first.move(Stage.SCHEDULED,"scheduler-a")
            a.save(first)
            second.move(Stage.SCHEDULED,"scheduler-b")
            with self.assertRaises(ValueError):
                b.save(second)
            self.assertEqual(a.load(case.id).events[0]["actor"],"scheduler-a")
            with self.assertRaises(ValueError):
                a.save(first)
            a.close()
            b.close()

    def test_service_identity_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"cases.db")
            case=Case.open("workshop")
            store.save(case)
            case.move(Stage.SCHEDULED,"staff")
            case.service="insurance_quote"
            with self.assertRaises(ValueError):
                store.save(case)
            store.close()
