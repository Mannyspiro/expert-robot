"""Exercise both supported package roots in fresh processes and real stores."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = """
import importlib
import json
from pathlib import Path
import sys
import tempfile

prefix, mode = sys.argv[1:]
bridge_prefix = 'python.dot_ai_os' if prefix == 'python.merlin' else 'dot_ai_os'
app = importlib.import_module(prefix + '.app')
reader = importlib.import_module(prefix + '.learning_evidence')
config = importlib.import_module(prefix + '.learning_research_config')
registry = importlib.import_module(prefix + '.project_registry')
artifact = importlib.import_module(prefix + '.artifact_ref')
bridge = importlib.import_module(bridge_prefix + '.bridge')
evidence = importlib.import_module(prefix + '.research_evidence')
assert bridge.MerlinRegistry is registry.MerlinRegistry
assert bridge.ArtifactRef is artifact.ArtifactRef
assert reader.MerlinRegistry is registry.MerlinRegistry
assert evidence.ArtifactRef is artifact.ArtifactRef
assert config.LearningEvidenceService is reader.LearningEvidenceService
assert app.LearningResearchAPI.__module__ == prefix + '.learning_research_api'
other_prefix = 'merlin' if prefix == 'python.merlin' else 'python.merlin'
assert other_prefix not in sys.modules
result = {'package': prefix, 'canonical_types_shared': True}
if mode == 'demos':
    evaluator = importlib.import_module(prefix + '.learning_evidence_eval')
    course = importlib.import_module(prefix + '.learning_titan_course')
    assert evaluator.DotContextBridge is bridge.DotContextBridge
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        first = evaluator.run_synthetic_evidence_demo(root / 'evidence', 'f' * 40)
        replay = evaluator.run_synthetic_evidence_demo(root / 'evidence', 'f' * 40)
        assert first == replay
        assert first['metrics']['passed'] == 4
        titan = course.run_synthetic_titan_demo(root / 'titan', 'f' * 40)
        again = course.run_synthetic_titan_demo(root / 'titan', 'f' * 40)
        assert titan['submission']['status'] == 'pending_review'
        assert again['submission']['duplicate'] is True
        assert titan['lab'] == again['lab']
        assert titan['mastery_updated'] is False
        assert titan['promotion_authority'] is False
        result['evidence_cases_passed'] = 4
        result['titan_submission_status'] = titan['submission']['status']
print(json.dumps(result, sort_keys=True))
"""


class LearningPackageImportTests(unittest.TestCase):
    def check_mode(self, prefix, mode):
        package_root = ROOT if prefix == 'python.merlin' else ROOT / 'python'
        environment = {
            'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
            'PYTHONPATH': str(package_root),
            'PYTHONNOUSERSITE': '1',
            'PYTHONDONTWRITEBYTECODE': '1',
        }
        # An empty unrelated working directory prevents the repository root
        # from becoming an accidental second package search path.
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, '-s', '-c', PROGRAM, prefix, mode],
                cwd=directory, env=environment, capture_output=True,
                text=True, timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr[-6000:])
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['package'], prefix)
        self.assertIs(receipt['canonical_types_shared'], True)
        if mode == 'demos':
            self.assertEqual(receipt['evidence_cases_passed'], 4)
            self.assertEqual(receipt['titan_submission_status'], 'pending_review')

    def test_top_level_imports_share_canonical_types(self):
        self.check_mode('merlin', 'imports')

    def test_repository_root_only_imports_share_canonical_types(self):
        self.check_mode('python.merlin', 'imports')

    def test_top_level_evidence_and_titan_replay(self):
        self.check_mode('merlin', 'demos')

    def test_repository_root_only_evidence_and_titan_replay(self):
        self.check_mode('python.merlin', 'demos')


if __name__ == '__main__':
    unittest.main()
