import unittest
from wilborn_ops.workflow import Case, Stage

class WorkflowTest(unittest.TestCase):
    def test_lifecycle(self):
        case=Case.open("document_signing")
        case.move(Stage.SCHEDULED,"scheduler")
        case.move(Stage.IN_SERVICE,"staff")
        with self.assertRaises(PermissionError):
            case.move(Stage.COMPLETED,"merlin")
        case.move(Stage.COMPLETED,"staff",approved=True)
        case.move(Stage.FOLLOW_UP,"staff")
        case.move(Stage.CLOSED,"staff",approved=True)
        self.assertTrue(case.verify())

    def test_invalid(self):
        case=Case.open("workshop")
        with self.assertRaises(ValueError): case.move(Stage.CLOSED,"staff",approved=True)
        with self.assertRaises(ValueError): Case.open("unknown")
        with self.assertRaises(ValueError): case.move(Stage.SCHEDULED,"")

    def test_tampering(self):
        case=Case.open("insurance_quote")
        case.move(Stage.SCHEDULED,"staff")
        case.events[0]["actor"]="altered"
        self.assertFalse(case.verify())

if __name__=="__main__": unittest.main()
