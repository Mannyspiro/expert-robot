"""Self-proposal, independent oracle and candidate-training orchestration contracts."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"python"))
from merlin import self_training_loop as loop


class FakeResponse:
    status=200
    def __init__(self,body):
        self._raw=body
    def read(self,count):
        return self._raw[:count]


class FakeConnection:
    calls=[]
    def __init__(self,*args,**kwargs):
        FakeConnection.calls.append((args,kwargs))
        self.args=None
    def request(self,*args,**kwargs):
        self.args=(args,kwargs)
    def getresponse(self):
        return FakeResponse(json.dumps({"choices":[{"message":{"content":json.dumps({
            "schema":"merlin-arithmetic-candidate/1",
            "examples":[
                {"operator":"mul","a":7,"b":13,"answer":91},
                {"operator":"sub","a":9,"b":3,"answer":6}
            ]})}}]}).encode())
    def close(self):
        pass


class SelfTrainingLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.out=root/"private"
        self.out.mkdir()
        self.holdout=root/"heldout.json"
        self.holdout.write_text(json.dumps([
            {"id":"held.1","question":"Compute 5 plus 8. Respond with only the integer.","answer":"13"},
            {"id":"held.2","question":"Compute 6 times 11. Respond with only the integer.","answer":"66"}
        ]))

    def test_proposal_only_loopback_and_small_answer(self):
        FakeConnection.calls=[]
        with patch.object(loop.http.client,"HTTPConnection",FakeConnection):
            raw=loop.propose_from_local_model(
                "http://127.0.0.1:8772/v1/chat/completions","local")
        self.assertIn("merlin-arithmetic-candidate/1",raw)
        self.assertEqual(FakeConnection.calls[0][0][:2],("127.0.0.1",8772))
        with self.assertRaises(ValueError):
            loop.propose_from_local_model("http://example.com:8772/v1/chat/completions","local")

    def test_oracle_prepares_usable_train_data_without_heldout_labels(self):
        response=json.dumps({
            "schema":"merlin-arithmetic-candidate/1",
            "examples":[
                {"operator":"mul","a":7,"b":13,"answer":91},
                {"operator":"sub","a":9,"b":3,"answer":6}
            ]})
        scratch=self.out/"scratch"
        scratch.mkdir()
        file,receipt=loop.prepare_verified_data(response,self.holdout,scratch)
        self.assertTrue(file.is_file())
        self.assertEqual(len(json.loads(file.read_text())),2)
        self.assertEqual(receipt["training_count"],2)
        self.assertNotIn("holdout",json.dumps(json.loads(file.read_text())))
        altered=response.replace('"answer": 91','"answer": 92')
        with self.assertRaises(ValueError):
            loop.prepare_verified_data(altered,self.holdout,scratch)

    def test_self_loop_requires_explicit_sha_and_does_not_replace_source(self):
        with self.assertRaises(ValueError):
            loop.run(endpoint="http://127.0.0.1:8772/v1/chat/completions",
                     model_id="local",expected_gguf_sha256="bad",
                     model_dir=self.out,holdout_path=self.holdout,
                     output_parent=self.out)
        self.assertEqual(list(self.out.iterdir()),[])

    def test_main_denies_implicit_model_execution(self):
        with self.assertRaises(ValueError):
            loop.main(["--endpoint","http://127.0.0.1:8772/v1/chat/completions",
                       "--expected-gguf-sha256","a"*64,
                       "--trainable-checkpoint-dir",str(self.out),
                       "--heldout-json",str(self.holdout),
                       "--candidate-parent",str(self.out)])


if __name__=="__main__":
    unittest.main(verbosity=2)
