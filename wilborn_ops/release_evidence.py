"""Read-only deployment gate. It cannot authorize or execute deployment."""
from copy import deepcopy
import re
from python.merlin.artifact_ref import ArtifactRef
from .attestation_boundary import fresh_attestation

REQUIRED_GATES=("native_build","authenticated_retrieval","independent_source_review",
                "data_isolation","host_authentication","titan_crypto_qualification",
                "artex_framework_qualification","restore_drill","connector_pilot",
                "independent_security_review","release_approval")

class ReleaseEvidenceGate:
    def __init__(self,*,trusted_by_gate,requester_id):
        if type(trusted_by_gate) is not dict or set(trusted_by_gate)-set(REQUIRED_GATES):
            raise ValueError("unknown release gate")
        if not requester_id:
            raise ValueError("requester identity required")
        self._trust=deepcopy(trusted_by_gate)
        self._requester=requester_id

    def report(self,*,source_commit,release_ref,attestations):
        if not isinstance(source_commit,str) or not re.fullmatch("[0-9a-f]{40}",source_commit):
            raise ValueError("exact source commit required")
        ref=ArtifactRef.from_mapping(release_ref)
        if type(attestations) is not dict or set(attestations)-set(REQUIRED_GATES):
            raise ValueError("unknown release evidence")
        # A synthetic/demo release can never acquire production readiness.
        if ref.project_id!="wilborn-production" or not ref.logical_path.startswith("releases/"):
            raise PermissionError("production release identity required")
        passed=[]
        blocked=[]
        for gate in REQUIRED_GATES:
            envelope=attestations.get(gate)
            trust=self._trust.get(gate)
            if not envelope or not trust:
                blocked.append(gate)
                continue
            bindings={"schema":"wilborn-release-evidence/1","scope":"production",
                      "source_commit":source_commit,"release_ref":ref.to_dict(),
                      "gate":gate,"outcome":"pass","deployment_authorized":False}
            fresh_attestation(envelope,trust=trust,claim_id="wilborn:release:"+gate,
                bundle_sha256=ref.sha256,bindings=bindings,requester_id=self._requester,
                purpose="independent-reproduction",max_age_seconds=86400)
            passed.append(gate)
        return {"schema":"wilborn-release-gate-report/1","source_commit":source_commit,
                "release_ref":ref.to_dict(),"signed_gate_statements":passed,
                "blocked_gates":blocked,"evidence_complete":not blocked,
                "production_qualified":False,"deployment_authorized":False,
                "note":"Separate host qualification and authorized deployment are required."}
