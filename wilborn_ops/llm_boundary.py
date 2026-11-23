"""Fail-closed synthetic-only LLM tool boundary prototype.

Artex is an LLM security framework, not an agent. This is an integration seam,
NOT a claim to implement the actual Artex framework or prevent prompt injection.
"""
from dataclasses import dataclass
from .gateway import BusinessGateway, Identity

ALLOWED_TOOLS=frozenset({"list_cases","get_case_status","service_metrics"})
MAX_CASE_ID_LENGTH=64

@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict

def dispatch(gateway: BusinessGateway, identity: Identity, call: ToolCall, *, artex_verified=False):
    if not artex_verified:
        raise PermissionError("Artex security verification required")
    if not isinstance(call, ToolCall) or call.name not in ALLOWED_TOOLS:
        raise PermissionError("tool not allowlisted")
    if not isinstance(call.arguments, dict):
        raise ValueError("invalid arguments")
    if call.name == "get_case_status":
        if set(call.arguments) != {"case_id"}:
            raise ValueError("invalid tool schema")
        case_id=call.arguments["case_id"]
        if not isinstance(case_id,str) or not case_id or len(case_id)>MAX_CASE_ID_LENGTH:
            raise ValueError("invalid case id")
        return gateway.get_case_status(identity,case_id)
    if call.arguments:
        raise ValueError("unexpected tool arguments")
    if call.name=="list_cases":
        return gateway.list_cases(identity)
    return gateway.service_metrics(identity)
