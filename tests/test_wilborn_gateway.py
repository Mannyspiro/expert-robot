import tempfile
import unittest
from pathlib import Path
from wilborn_ops.gateway import BusinessGateway, Identity
from wilborn_ops.store import CaseStore
from wilborn_ops.workflow import Case

class GatewayTests(unittest.TestCase):
    def test_scopes_tenant_and_data_minimization(self):
        with tempfile.TemporaryDirectory() as folder:
            store=CaseStore(Path(folder)/"demo.db")
            case=Case.open("workshop")
            store.save(case)
            gateway=BusinessGateway(store)
            reader=Identity("staff-1","wilborn-demo",frozenset({"cases:read"}))
            self.assertEqual(gateway.get_case_status(reader,case.id)["stage"],"intake")
            self.assertEqual(len(gateway.list_cases(reader)),1)
            self.assertEqual(set(gateway.list_cases(reader)[0]),{"id","service","stage"})
            with self.assertRaises(PermissionError):
                gateway.service_metrics(reader)
            with self.assertRaises(PermissionError):
                gateway.list_cases(Identity("staff-1","other-tenant",frozenset({"cases:read"})))
            with self.assertRaises(PermissionError):
                gateway.list_cases(Identity("staff-1","wilborn-demo",frozenset()))
            metrics=Identity("staff-2","wilborn-demo",frozenset({"metrics:read"}))
            self.assertEqual(gateway.service_metrics(metrics)["total_cases"],1)
            with self.assertRaises(PermissionError):
                gateway.list_cases(metrics)
            store.close()
