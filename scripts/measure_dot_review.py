"""Measure three fixed retrieval policies on pinned Merlin operating documents."""
import argparse
import json
from pathlib import Path

from dot_ai_os.bridge import DotContextBridge, canonical, digest
from dot_ai_os.cross_agent_review import CrossAgentReviewer
from merlin.project_registry import MerlinRegistry


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "54973bd683021a5566aa197bdc510d4f3bca20a1"
FILES = {
    "AGENTS.md": ("merlin", "6fd6de36b30f5693aebff2cf326ebfc302d47ee24055aaab7abce8c000aff6d2"),
    "docs/MERLIN_AVREA_HERMES_ROUTING.md": ("merlin", "f1dcf2f6af9dae77c9233fea0ceb7c81e07e513a2dffd0ea68627f170b166308"),
    "docs/cace-bidirectional-bridge.md": ("morgana-cace", "a28f011ad3e92ca7e764056119113ecddc8cde26a28daad5918756f72d7eb73e"),
}
AGENTS, ROUTING, BRIDGE = FILES
# Freeze split, query, host-pinned document, and expected first locator before execution.
CASES = {
    "train-in-scope": ("train", "abduction", AGENTS, AGENTS),
    "train-cross-namespace": ("train", "ed25519", AGENTS, "no_hit"),
    "held-routing": ("holdout", "workflow_dispatch", ROUTING, ROUTING),
    "held-cross-namespace": ("holdout", "Mathlib", AGENTS, "no_hit"),
    "held-sibling-routing": ("holdout", "federation", AGENTS, "no_hit"),
    "held-sibling-agents": ("holdout", "uncertainty", ROUTING, "no_hit"),
    "held-bridge": ("holdout", "unsigned", BRIDGE, BRIDGE),
}


def run(registry_path):
    registry = MerlinRegistry(registry_path)
    project = "dot-retrieval-review-v1"
    bridge = DotContextBridge(registry, project_id=project)
    bridge.initialize()
    pins = {}
    for path, (namespace, expected_hash) in FILES.items():
        data = (ROOT / path).read_bytes()
        if digest(data) != expected_hash:
            raise ValueError(f"source differs from pinned document: {path}")
        stored = bridge.ingest(namespace=namespace, source_id=path, title=path, content=data,
            source_url=f"https://github.com/Mannyspiro/expert-robot/blob/{COMMIT}/{path}",
            source_version=COMMIT, epistemic="source_snapshot", captured_at="2026-11-18T00:00:00Z")
        pins[path] = {k: stored[k] for k in ("record_ref", "source_ref")}
    if bridge.status()["record_count"] != len(FILES):
        raise ValueError("benchmark project contains other source documents")
    source_paths = ["python/dot_ai_os/bridge.py", "python/dot_ai_os/cross_agent_review.py",
                    "python/dot_ai_os/dual_coder.py", "scripts/measure_dot_review.py"]
    sources = {p: digest((ROOT / p).read_bytes()) for p in source_paths}
    source_path = "benchmarks/retrieval/baseline.json"
    registry.put_artifact(project, source_path, canonical({"policy": "global", "sources": sources}))
    baseline = registry.artifact_ref(project, source_path)
    reviewers = CrossAgentReviewer(registry, project_id=project)
    policies = {"coder_a": "namespace", "coder_b": "host_pin", "evaluator": "capture_top_locator"}
    providers = {role: {"provider_id": "fixed-software-" + role, "revision": sources[source_paths[-1]],
        "prompt_sha256": digest(canonical({"prompt": None})), "config_sha256": digest(canonical(policy)),
        "adapter_sha256": sources[source_paths[-1]]} for role, policy in policies.items()}
    labels = {split: {key: value[3] for key, value in CASES.items() if value[0] == split}
              for split in ("train", "holdout")}
    protocol = reviewers.prepare(target="dot", baseline_ref=baseline,
        context_refs=[pin["source_ref"] for pin in pins.values()],
        objective="Return the first matching locator inside the host-selected document, or no_hit.",
        source_commit=COMMIT, providers=providers, train_labels=labels["train"], holdout_labels=labels["holdout"])

    def propose(req):
        return {"candidate": policies[req["stage"]], "rationale": "Predeclared retrieval-scope policy."}

    def observe(req):
        results = {}
        for arm in ("baseline", "coder_a", "coder_b"):
            policy = "global" if arm == "baseline" else req["candidates"][arm]["candidate"]
            results[arm] = {}
            for key, (_, query, allowed, _) in CASES.items():
                if policy == "host_pin":
                    scope = {"pinned_records": [pins[allowed]]}
                elif policy == "namespace":
                    scope = {"namespace": FILES[allowed][0]}
                elif policy == "global":
                    scope = {}
                else:
                    raise ValueError("unknown retrieval policy")
                hits = bridge.search(query, limit=1, **scope)["hits"]
                results[arm][key] = hits[0]["title"] if hits else "no_hit"
        return results

    result = reviewers.run(protocol, coder_a=propose, coder_b=propose, observe=observe)
    if "observation_ref" not in result:
        raise ValueError("measurement incomplete; inspect the registry workflow before retrying")
    obs = json.loads(registry.read_artifact_ref(result["observation_ref"])["content"])
    return {"schema": "dot-retrieval-review-benchmark/1", "target": "dot", "sources": sources,
            "source_commit": COMMIT, "input_documents_sha256": {p: h for p, (_, h) in FILES.items()},
            "scope": "local_product_behavior_fixed_software_adapters", "protocol_ref": protocol,
            "observations_ref": result["observation_ref"], "report_ref": result["workflow"]["report_ref"],
            "cases": {k: {"split": v[0], "query": v[1], "host_document": v[2], "expected": v[3],
                          "observed": {arm: values[k] for arm, values in obs["predictions"].items()}}
                      for k, v in CASES.items()},
            "scores": result["scores"], "outcomes": result["outcomes"], "recommendation": result["recommendation"],
            "qualification": False, "promotion_authority": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, help="Local persistent Merlin registry directory")
    args = parser.parse_args()
    print(json.dumps(run(args.registry), indent=2, sort_keys=True))
