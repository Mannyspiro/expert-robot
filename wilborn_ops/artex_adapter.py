"""Fail-closed signed-verdict seam for a host-supplied Artex framework.

This is not the Artex framework implementation. No production credentials or
client records; fixture validation does not qualify Artex itself.
"""
from copy import deepcopy
import re
import secrets
from .attestation_boundary import digest,fresh_attestation
from .gateway import Identity
from .llm_boundary import ToolCall,ALLOWED_TOOLS

CLAIM="wilborn:artex:tool-verdict:v1"

def verdict_bindings(request,decision,version,policy_sha256):
    return {"schema":"wilborn-artex-verdict/1","scope":"synthetic_fixture",
            "framework":"Artex","version":version,"policy_sha256":policy_sha256,
            "request_sha256":digest(request),"decision":decision}

class SignedArtexAdapter:
    def __init__(self,provider,*,version,policy_sha256,trust,requester_id):
        if not callable(provider) or not trust or not requester_id:
            raise PermissionError("host-configured framework and pinned signer required")
        if not isinstance(version,str) or not 1<=len(version)<=128:
            raise ValueError("framework version required")
        if not isinstance(policy_sha256,str) or not re.fullmatch("[0-9a-f]{64}",policy_sha256):
            raise ValueError("pinned policy hash required")
        self._provider=provider
        self._version=version
        self._policy=policy_sha256
        self._trust=deepcopy(trust)
        self._requester=requester_id

    def verify(self,identity,call):
        if type(identity) is not Identity or identity.tenant!="wilborn-demo":
            return False
        if type(call) is not ToolCall or call.name not in ALLOWED_TOOLS:
            return False
        request={"schema":"wilborn-artex-request/1","scope":"synthetic_fixture",
                 "nonce":secrets.token_hex(16),"subject":identity.subject,
                 "tenant":identity.tenant,"scopes":sorted(identity.scopes),
                 "tool":call.name,"arguments":deepcopy(call.arguments)}
        request_hash=digest(request)
        response=self._provider(deepcopy(request))
        if type(response) is not dict or set(response)!={"decision","attestation"}:
            return False
        decision=response["decision"]
        if decision not in ("allow","deny"):
            return False
        bindings=verdict_bindings(request,decision,self._version,self._policy)
        fresh_attestation(response["attestation"],trust=self._trust,claim_id=CLAIM,
            bundle_sha256=request_hash,bindings=bindings,requester_id=self._requester,
            purpose="artifact-integrity",max_age_seconds=60)
        return decision=="allow"
