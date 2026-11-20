"""Score isolated application observations with dot's existing review workflow.

Input observations are produced by the independent local evaluator. The fixed
adapters below publish hashes of proposed source; they do not execute that source.
"""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from dot_ai_os.bridge import DotContextBridge, canonical
from dot_ai_os.cross_agent_review import CrossAgentReviewer
from merlin.project_registry import MerlinRegistry

COMMIT = "e7be083b754b36e90d9ebffbe9f7ef9069296e06"
ARMS = ("baseline", "coder_a", "coder_b")


def digest(raw):
    return sha256(raw).hexdigest()


def run(matrix, base, first, second):
    blobs = dict(zip(ARMS, (base.read_bytes(), first.read_bytes(), second.read_bytes())))
    paths = {
        arm: {"sha256": digest(raw), "description": description}
        for (arm, raw), description in zip(blobs.items(), (
            "Existing Pillow identification and PNG postcheck",
            "Allowlist PNG at both Image.open calls",
            "Preflight PNG signature and bound IHDR before Pillow",
        ))
    }
    adapter = digest(Path(__file__).read_bytes())
    providers = {
        role: {
            "provider_id": role + "-20261119",
            "revision": paths.get(role, {}).get("sha256", digest(canonical(matrix["observed"]))),
            "prompt_sha256": digest(canonical(None)),
            "config_sha256": digest(canonical(role)),
            "adapter_sha256": adapter,
        }
        for role in ("coder_a", "coder_b", "evaluator")
    }

    with tempfile.TemporaryDirectory() as temporary:
        project = "drafting-png-review"
        registry = MerlinRegistry(temporary)
        DotContextBridge(registry, project_id=project).initialize()
        source_path = "drafting/pr178/baseline.py"
        registry.put_artifact(project, source_path, blobs["baseline"], "text/plain")
        reviewer = CrossAgentReviewer(registry, project_id=project)
        protocol = reviewer.prepare(
            target="merlin",
            baseline_ref=registry.artifact_ref(project, source_path),
            context_refs=[],
            objective="Only dispatch PNG decoding for the drafting review and preserve the source-bound decision.",
            source_commit=COMMIT,
            providers=providers,
            train_labels=matrix["train"],
            holdout_labels=matrix["holdout"],
        )

        def propose(request):
            pin = paths[request["stage"]]
            return {"candidate": pin["sha256"], "rationale": pin["description"]}

        def observe(request):
            for arm in ARMS[1:]:
                if request["candidates"][arm]["candidate"] != paths[arm]["sha256"]:
                    raise ValueError("Wrong measured candidate")
            return matrix["observed"]

        result = reviewer.run(protocol, coder_a=propose, coder_b=propose, observe=observe)
        for name in ("observation_ref", "scores"):
            if name not in result:
                raise RuntimeError(f"Review missing {name}")
        return {
            "source_commit": COMMIT,
            "sources": paths,
            "matrix_sha256": digest(canonical(matrix)),
            "protocol_ref": protocol,
            "observation_ref": result["observation_ref"],
            "report_ref": result["workflow"]["report_ref"],
            "scores": result["scores"],
            "recommendation": result["recommendation"],
            "model_calls": 0,
            "scope": "Fixed adapters scoring actual local fixture observations. No promotion authority.",
        }


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for field in ("matrix", *ARMS):
        parser.add_argument(field, type=Path)
    args = parser.parse_args()
    inputs = json.loads(args.matrix.read_text())
    print(json.dumps(run(inputs, args.baseline, args.coder_a, args.coder_b), indent=2))
