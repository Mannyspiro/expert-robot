"""Exercise the frozen browser publisher's real wire format with its fake renderer.

This local compatibility check performs no browser, network or model call. Paths
are verification inputs only; the production coordinator has fixed installed pins.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-source", required=True)
    parser.add_argument("--browser-source", required=True)
    parser.add_argument("--program", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    private, browser = Path(args.private_source), Path(args.browser_source)
    sys.path.insert(0, str(private / "python"))
    import merlin
    merlin.__path__.append(str(Path(__file__).resolve().parents[1] / "python/merlin"))
    merlin.__path__.append(str(browser / "python/merlin"))
    from merlin.project_registry import MerlinRegistry
    from merlin.browser_ingest import publish_episode
    from merlin.browser_research_handoff import BrowserResearchHandoff, PROJECT, SCHEMA
    spec = importlib.util.spec_from_file_location("frozen_browser_fixture", browser / "tests/test_public_browser.py")
    fixture_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture_module)
    urls = ["https://example.org/source", "https://example.org/search?q=rank", "http://example.org/data"]
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        fixture_module.fixture(root / "episode", episode="wire-fixture",
                               actions=[{"action": "open", "url": url} for url in urls])
        registry = MerlinRegistry(root / "registry")
        publication = publish_episode(root / "episode", registry)
        request = {"schema": SCHEMA, "request_id": str(uuid.uuid4()), "episode_id": "wire-fixture",
                   "publication_ref": registry.artifact_ref(PROJECT, "browser/episodes/wire-fixture/publication.json")}
        # This new module is not published yet; do not attribute it to the older browser commit.
        fixture_source_commit = "b" * 40
        worker = BrowserResearchHandoff(registry, source_commit=fixture_source_commit,
                    program_bytes=Path(args.program).read_bytes(), authorize=lambda operation, binding: True)
        answer = worker.submit(request)
        assert answer["status"] == "recorded", answer
        result = answer["result"]
        measurement = json.loads(registry.read_artifact_ref(result["measurement_ref"])["content"])
        plan = json.loads(registry.read_artifact_ref(result["plan_ref"])["content"])
        review = json.loads(registry.read_artifact_ref(result["review_ref"])["content"])
        assert [row["acquisition_url"] for row in measurement["captures"]] == urls
        assert measurement["counts"]["captures"] == measurement["counts"]["usable_captures"] == 3
        assert measurement["counts"]["reported_bridge_source_snapshots"] == 1
        child_code = '''import importlib.util, json, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'python'))
from merlin.project_registry import MerlinRegistry
spec = importlib.util.spec_from_file_location('merlin.browser_research_handoff', sys.argv[2])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
worker = module.BrowserResearchHandoff(MerlinRegistry(sys.argv[3]), source_commit='b' * 40,
    program_bytes=pathlib.Path(sys.argv[4]).read_bytes(), authorize=lambda operation, binding: True)
print(json.dumps({'pid': os.getpid(), 'response': worker.status(sys.argv[5])}, sort_keys=True))
'''
        module_file = Path(__file__).resolve().parents[1] / "python/merlin/browser_research_handoff.py"
        child = subprocess.run([sys.executable, "-I", "-B", "-c", child_code, str(private), str(module_file),
                                str(root / "registry"), str(Path(args.program).resolve()), request["request_id"]],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                               env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"})
        assert child.returncode == 0, child.stderr.decode()
        child_output = json.loads(child.stdout)
        assert child_output["pid"] != os.getpid()
        replay = child_output["response"]
        assert replay["result_ref"] == answer["result_ref"] and replay["result"] == result
        files = [browser / "tests/test_public_browser.py", browser / "python/merlin/browser_ingest.py",
                 private / "python/dot_ai_os/research_protocol.py", private / "python/merlin/scientific_loop.py",
                 Path(__file__).resolve().parents[1] / "python/merlin/browser_research_handoff.py", Path(args.program)]
        report = {"schema": "merlin-browser-handoff-wire-compatibility/1", "status": "passed",
                  "scope": "actual frozen publisher and canonical research APIs with a synthetic fake-renderer fixture",
                  "actual_browser_executed": False, "native_execution_accepted": False,
                  "plan_source_commit_scope": "synthetic caller declaration for this local fixture; actual files bound separately",
                  "frozen_browser_source_commit": "8e2f1d69371d5b4f7e01e3bbd5aa02a666ddd506",
                  "new_browser_calls": 0, "model_calls": 0, "expected_exact_urls": urls,
                  "source_bindings": [{"path": str(path), "bytes": len(path.read_bytes()),
                                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files],
                  "request": request, "publication": publication, "result": result,
                  "measurement": measurement, "plan": plan, "review": review,
                  "restart_same_result_ref": replay["result_ref"],
                  "restart_process": {"parent_pid": os.getpid(), "child_pid": child_output["pid"],
                                      "isolated_python": True, "exit_code": child.returncode,
                                      "read_only_status_operation": True, "response": replay,
                                      "stdout_sha256": hashlib.sha256(child.stdout).hexdigest(),
                                      "stderr_sha256": hashlib.sha256(child.stderr).hexdigest()},
                  "fixture_registry_scope": "temporary local synthetic store; references are not production references"}
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"status": "passed", "captures": 3, "usable_captures": 3,
                          "reported_bridge_source_snapshots": 1, "restart_same_result": True,
                          "fresh_process_readback": True,
                          "new_browser_calls": 0, "model_calls": 0, "report": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
