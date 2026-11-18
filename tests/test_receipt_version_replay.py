import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "python"), str(ROOT / "scripts/merlin")]
from ask_receipt import ask
from dot_ai_os.bridge import DotContextBridge
from merlin.project_registry import MerlinRegistry


class ReceiptVersionReplay(unittest.TestCase):
    def test_restart_resolves_each_exact_version(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = DotContextBridge(MerlinRegistry(Path(directory)))
            bridge.initialize()
            refs = []
            for version, count in enumerate((12, 31), start=1):
                data = json.dumps({"run_id":"1001","tests":{"tests":count}}).encode()
                refs.append(bridge.ingest(namespace="merlin",source_id="sample-run",
                    title="Synthetic learning run",content=data,source_url="https://example.org/run",
                    source_version=str(version),epistemic="historical_report",
                    captured_at="2026-11-18T00:00:00Z")["source_ref"])
            reopened = DotContextBridge(MerlinRegistry(Path(directory)))
            for ref, count in zip(refs,(12,31)):
                with self.subTest(version=ref["version"]):
                    result = ask(reopened, {"1001":ref}, "For run 1001, how many main shard tests ran?")
                    self.assertEqual(result["disposition"], "supported")
                    self.assertEqual(result["value"], count)
                    self.assertEqual(result["citation"], {"source_ref":ref,"pointer":"/tests/tests"})
            wrong = ask(reopened, {"1002":refs[0]}, "For run 1002, how many main shard tests ran?")
            self.assertEqual(wrong["disposition"], "abstain")
