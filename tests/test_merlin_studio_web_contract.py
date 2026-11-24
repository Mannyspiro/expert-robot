"""Run the actual standalone renderer and event-state functions under Node."""
from pathlib import Path
import json
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class StudioWebContract(unittest.TestCase):
    def test_untrusted_rendering_and_replay_contract(self):
        result=subprocess.run(['node',str(ROOT/'tests/merlin_studio_web_contract.cjs')],
                              cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['passed'],6)
        self.assertTrue(all(case['passed'] for case in report['results']))

if __name__=='__main__': unittest.main()
