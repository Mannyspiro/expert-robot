import unittest
from wilborn_ops.provenance import DataClass, Provenance, assert_demo, response_envelope

class ProvenanceTests(unittest.TestCase):
    def test_demo_response_always_labeled(self):
        p=Provenance(DataClass.SYNTHETIC,"demo","unit-test")
        result=response_envelope({"cases":[]},p)
        self.assertEqual(result["data_class"],"synthetic")
        self.assertFalse(result["verified_real"])

    def test_cross_environment_and_unknown_rejected(self):
        with self.assertRaises(ValueError):
            Provenance(DataClass.REAL,"demo","import",True)
        with self.assertRaises(ValueError):
            Provenance(DataClass.SYNTHETIC,"production","import")
        with self.assertRaises(ValueError):
            Provenance(DataClass.REAL,"production","unverified")
        with self.assertRaises(ValueError):
            Provenance(DataClass.SYNTHETIC,"unknown","fixture")
        with self.assertRaises(PermissionError):
            assert_demo(None)
        with self.assertRaises(PermissionError):
            assert_demo(Provenance(DataClass.REAL,"production","verified-import",True))
