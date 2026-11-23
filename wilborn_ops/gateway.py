"""Synthetic-data business gateway. No network or production authority."""
from dataclasses import dataclass
from .store import CaseStore
from .workflow import SERVICES

@dataclass(frozen=True)
class Identity:
    subject: str
    tenant: str
    scopes: frozenset

    def __post_init__(self):
        if not self.subject or not self.tenant:
            raise ValueError("authenticated subject and tenant required")

class BusinessGateway:
    def __init__(self, store, tenant="wilborn-demo"):
        self.store=store
        self.tenant=tenant

    def _authorize(self, identity, scope):
        if not isinstance(identity, Identity) or identity.tenant != self.tenant:
            raise PermissionError("tenant or identity denied")
        if scope not in identity.scopes:
            raise PermissionError("scope denied")

    def list_cases(self, identity):
        self._authorize(identity, "cases:read")
        return [{"id":c.id, "service":c.service, "stage":c.stage.value}
                for c in self.store.list_cases()]

    def get_case_status(self, identity, case_id):
        self._authorize(identity, "cases:read")
        case=self.store.load(case_id)
        return {"id":case.id, "service":case.service, "stage":case.stage.value}

    def service_metrics(self, identity):
        self._authorize(identity, "metrics:read")
        cases=self.store.list_cases()
        # Only synthetic demonstration records. Production requires privacy thresholds.
        return {"total_cases":len(cases),
                "by_service":{service:sum(c.service==service for c in cases)
                              for service in sorted(SERVICES)}}
