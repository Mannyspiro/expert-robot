"""Synthetic-only business gateway; never represents demo results as real."""
from dataclasses import dataclass
from .workflow import SERVICES
from .provenance import assert_demo, response_envelope

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
        assert_demo(store.provenance)
        self.store=store
        self.tenant=tenant

    def _authorize(self, identity, scope):
        assert_demo(self.store.provenance)
        if not isinstance(identity, Identity) or identity.tenant != self.tenant:
            raise PermissionError("tenant or identity denied")
        if scope not in identity.scopes:
            raise PermissionError("scope denied")

    def _envelope(self, payload):
        return response_envelope(payload, self.store.provenance)

    def list_cases(self, identity):
        self._authorize(identity, "cases:read")
        return self._envelope([{"id":c.id,"service":c.service,"stage":c.stage.value}
                               for c in self.store.list_cases()])

    def get_case_status(self, identity, case_id):
        self._authorize(identity, "cases:read")
        case=self.store.load(case_id)
        return self._envelope({"id":case.id,"service":case.service,"stage":case.stage.value})

    def service_metrics(self, identity):
        self._authorize(identity, "metrics:read")
        cases=self.store.list_cases()
        return self._envelope({"total_cases":len(cases),
                "by_service":{service:sum(c.service==service for c in cases)
                              for service in sorted(SERVICES)}})
