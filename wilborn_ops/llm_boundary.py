"""Synthetic-only LLM tool boundary with fail-closed security adapter.

This is NOT the actual Artex framework and is not a production security boundary.
"""
from dataclasses import dataclass
from .gateway import BusinessGateway, Identity

ALLOWED_TOOLS=frozenset({"list_cases","get_case_status","service_metrics"})
MAX_CASE_ID_LENGTH=64

@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict

class SecurityUnavailable(Exception):
    pass

class DenyAllSecurityAdapter:
    def verify(self, identity, call):
        return False

class BusinessToolDispatcher:
    """Host configures adapter; untrusted tool calls cannot self-approve."""
    def __init__(self, gateway: BusinessGateway, security_adapter=None):
        self.gateway=gateway
        self._security=security_adapter or DenyAllSecurityAdapter()

    def dispatch(self, identity: Identity, call: ToolCall):
        if not isinstance(call,ToolCall) or call.name not in ALLOWED_TOOLS:
            raise PermissionError("tool not allowlisted")
        if not isinstance(call.arguments,dict):
            raise ValueError("invalid arguments")
        if call.name=="get_case_status":
            if set(call.arguments)!={"case_id"}:
                raise ValueError("invalid tool schema")
            case_id=call.arguments["case_id"]
            if not isinstance(case_id,str) or not case_id or len(case_id)>MAX_CASE_ID_LENGTH:
                raise ValueError("invalid case id")
        elif call.arguments:
            raise ValueError("unexpected tool arguments")

        # Actual Artex adapter must be installed by a trusted host, not the LLM.
        try:
            verified=self._security.verify(identity,call)
        except Exception as exc:
            raise SecurityUnavailable("security adapter unavailable") from exc
        if verified is not True:
            raise PermissionError("security verification denied")

        if call.name=="get_case_status":
            return self.gateway.get_case_status(identity,call.arguments["case_id"])
        if call.name=="list_cases":
            return self.gateway.list_cases(identity)
        return self.gateway.service_metrics(identity)
