"""Synthetic-only LLM tool boundary with fail-closed adapter and event telemetry.

Not actual Artex; no production authentication or live threat hunting.
"""
from dataclasses import dataclass
from .gateway import BusinessGateway, Identity
from .security_monitor import SecurityEvent

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
    """Host supplies adapters; untrusted calls cannot self-approve."""
    def __init__(self, gateway: BusinessGateway, security_adapter=None, monitor=None):
        self.gateway=gateway
        self._security=security_adapter if security_adapter is not None else DenyAllSecurityAdapter()
        self._monitor=monitor

    def _event(self, kind):
        if self._monitor is not None:
            # No user-supplied arguments, names, tokens, or prompt text are logged.
            self._monitor.observe(SecurityEvent(kind,"demo","synthetic"))

    def dispatch(self, identity: Identity, call: ToolCall):
        if not isinstance(call,ToolCall) or call.name not in ALLOWED_TOOLS:
            self._event("unexpected_tool")
            raise PermissionError("tool not allowlisted")
        if not isinstance(call.arguments,dict):
            self._event("tool_denied")
            raise ValueError("invalid arguments")
        call=ToolCall(call.name,dict(call.arguments))
        if call.name=="get_case_status":
            if set(call.arguments)!={"case_id"}:
                self._event("tool_denied")
                raise ValueError("invalid tool schema")
            case_id=call.arguments["case_id"]
            if not isinstance(case_id,str) or not case_id or len(case_id)>MAX_CASE_ID_LENGTH:
                self._event("tool_denied")
                raise ValueError("invalid case id")
        elif call.arguments:
            self._event("tool_denied")
            raise ValueError("unexpected tool arguments")

        try:
            verified=self._security.verify(identity,ToolCall(call.name,dict(call.arguments)))
        except Exception as exc:
            self._event("integrity_failure")
            raise SecurityUnavailable("security adapter unavailable") from exc
        if verified is not True:
            self._event("tool_denied")
            raise PermissionError("security verification denied")

        try:
            if call.name=="get_case_status":
                return self.gateway.get_case_status(identity,call.arguments["case_id"])
            if call.name=="list_cases":
                return self.gateway.list_cases(identity)
            return self.gateway.service_metrics(identity)
        except PermissionError:
            self._event("tool_denied")
            raise
