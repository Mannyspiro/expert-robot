"""Titan protocol lifecycle research model; no cryptographic primitives implemented."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True)
class TitanProfile:
    envelope_version: int = 1
    kdf: str = "HKDF-SHA-256"
    aead: str = "AES-256-GCM-SIV"
    kem: str | None = None
    context_binding: bool = True
    authenticated_metadata: bool = True

@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    description: str
    key_established: bool = True
    derivation_succeeds: bool = True
    seal_succeeds: bool = True
    authentication_succeeds: bool = True
    expected_terminal_state: str = "verified"

ALLOWED_KDFS = {"HKDF-SHA-256"}
ALLOWED_AEADS = {"AES-256-GCM-SIV"}
ALLOWED_KEMS = {None, "ML-KEM-768", "ML-KEM-1024"}

def validate_profile(profile: TitanProfile) -> list[str]:
    errors = []
    if profile.envelope_version != 1: errors.append("unsupported envelope version")
    if profile.kdf not in ALLOWED_KDFS: errors.append("KDF is not in reviewed profile allow-list")
    if profile.aead not in ALLOWED_AEADS: errors.append("AEAD is not in reviewed profile allow-list")
    if profile.kem not in ALLOWED_KEMS: errors.append("KEM is not in reviewed profile allow-list")
    if not profile.context_binding: errors.append("context binding is required")
    if not profile.authenticated_metadata: errors.append("metadata authentication is required")
    return errors

def default_scenarios() -> tuple[Scenario, ...]:
    return (
        Scenario("valid-round-trip", "All abstract protocol stages succeed."),
        Scenario("key-establishment-failure", "No shared secret established.", key_established=False, expected_terminal_state="rejected"),
        Scenario("derivation-failure", "Derivation fails closed.", derivation_succeeds=False, expected_terminal_state="rejected"),
        Scenario("seal-failure", "Envelope creation fails closed.", seal_succeeds=False, expected_terminal_state="rejected"),
        Scenario("authentication-failure", "Modified ciphertext or AAD is rejected.", authentication_succeeds=False, expected_terminal_state="rejected"),
    )

def simulate_lifecycle(profile: TitanProfile, scenario: Scenario) -> dict[str, Any]:
    """Abstract state-machine simulation only; cryptographic outcomes are injected."""
    errors = validate_profile(profile)
    if errors:
        return {"schema":"titan-protocol-simulation/1","scenario_id":scenario.scenario_id,
                "profile":asdict(profile),"states":["rejected"],"terminal_state":"rejected",
                "profile_errors":errors,"cryptographic_operations_performed":False}
    states = ["initialized"]
    if not scenario.key_established: states.append("rejected")
    else:
        states.append("key_established")
        if not scenario.derivation_succeeds: states.append("rejected")
        else:
            states.append("keys_derived")
            if not scenario.seal_succeeds: states.append("rejected")
            else:
                states.append("sealed")
                states.append("verified" if scenario.authentication_succeeds else "rejected")
    terminal = states[-1]
    return {"schema":"titan-protocol-simulation/1","scenario_id":scenario.scenario_id,
            "profile":asdict(profile),"states":states,"terminal_state":terminal,
            "expected_terminal_state":scenario.expected_terminal_state,
            "expectation_met":terminal == scenario.expected_terminal_state,"profile_errors":[],
            "cryptographic_operations_performed":False,
            "limitation":"No cryptographic primitive, entropy, side channel, or security proof is evaluated."}

def build_research_matrix() -> dict[str, Any]:
    profile = TitanProfile(kem="ML-KEM-768")
    return {"schema":"titan-cryptographic-research-matrix/1",
            "purpose":"Model protocol lifecycle and fail-closed requirements around a standards-based envelope.",
            "profile":asdict(profile),"profile_errors":validate_profile(profile),
            "scenarios":[simulate_lifecycle(profile,s) for s in default_scenarios()],
            "research_tracks":[
                {"id":"titan-context-binding","question":"Are canonical context fields versioned, unambiguous and authenticated as associated data?","evidence_needed":["canonical encoding spec","cross-language test vectors","negative metadata tests"]},
                {"id":"titan-hybrid-kem","question":"Can ML-KEM key establishment be integrated without inventing a key combiner?","evidence_needed":["current FIPS 203 errata review","SP 800-227 conformance","published hybrid combiner specification","independent review"]},
                {"id":"titan-key-lifecycle","question":"Are rotation, recipient changes, revocation and recovery explicit protocol states?","evidence_needed":["state-transition spec","recovery vectors","key-separation review"]},
                {"id":"titan-interoperability","question":"Do independent implementations consume identical canonical envelopes?","evidence_needed":["versioned public vectors","cross-implementation results","negative compatibility tests"]}],
            "promotion_rule":"No custom cipher promotion. Use published primitives; require independent cryptographic review and CACE verification."}

__all__=["TitanProfile","Scenario","validate_profile","default_scenarios","simulate_lifecycle","build_research_matrix"]


def register_titan_research(registry, graph, project_id: str,
                            logical_path: str = "research/titan/initial-matrix.json") -> dict[str, Any]:
    """Persist deterministic research output and provenance graph as unreviewed artifacts."""
    import hashlib
    import json
    from merlin.knowledge_graph import GraphEdge, GraphNode

    report = build_research_matrix()
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    digest = registry.put_artifact(project_id, logical_path, encoded, "application/json")
    if not registry.verify_artifact(digest):
        raise RuntimeError("Titan research artifact failed canonical registry verification")

    artifact_id = f"artifact:titan:{digest[:24]}"
    module_id = "module:merlin:titan-crypto-lab"
    registry.relate(module_id, "produces", artifact_id, {"sha256": digest, "status": "unreviewed"})
    graph.add_node(GraphNode(module_id, "module", "Titan Cryptographic Research Lab",
                             {"scope": "protocol-state simulation only", "status": "unreviewed"}))
    graph.add_node(GraphNode(artifact_id, "artifact", "Titan initial cryptographic research matrix",
                             {"sha256": digest, "logical_path": logical_path,
                              "schema": report["schema"], "status": "unreviewed"}))
    graph.add_edge(GraphEdge(module_id, "produces", artifact_id,
                             {"sha256": digest, "status": "unreviewed"}))
    return {"artifact_sha256": digest, "artifact_verified": True,
            "artifact_node_id": artifact_id, "module_node_id": module_id,
            "scenario_count": len(report["scenarios"]),
            "research_track_count": len(report["research_tracks"]),
            "evidence_class": "unreviewed",
            "claim": "Protocol lifecycle model generated; no cryptographic security claim."}


__all__.append("register_titan_research")


def hermes_titan_research_executor(task, context):
    """Injected Hermes research-stage executor; emits deterministic matrix bytes."""
    import json
    if task.get("stage") != "research":
        raise ValueError("Titan executor only accepts the research stage")
    objective = str(task.get("objective", "")).strip()
    if not objective or "titan" not in objective.lower():
        raise ValueError("task objective must explicitly identify Titan research")
    report = build_research_matrix()
    report["task"] = {
        "task_id": context.task_id,
        "hypothesis_id": context.hypothesis_id,
        "objective": objective,
    }
    payload = (json.dumps(report, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False) + "\n").encode()
    return {
        "artifact_bytes": payload,
        "media_type": "application/vnd.merlin.titan-research+json",
        "summary": "Generated deterministic Titan protocol research matrix; no cryptographic operations performed.",
        "metadata": {"artifact_schema": report["schema"],
                     "execution_mode": "deterministic_protocol_model",
                     "cryptographic_operations_performed": False},
    }


__all__.append("hermes_titan_research_executor")
