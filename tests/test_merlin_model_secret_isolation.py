"""Verify model subprocess environment never inherits host credentials."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"portable"/"merlin_studio"))
from model import isolated_model_environment, BundledModel


class IsolatedModelEnvironmentTests(unittest.TestCase):
    def test_repository_and_cloud_credentials_removed(self):
        source={"PATH":"/usr/bin","LANG":"C","HOME":"/tmp",
                "GITHUB_TOKEN":"sensitive-github",
                "GITLAB_TOKEN":"sensitive-gitlab",
                "CI_JOB_TOKEN":"sensitive-ci",
                "AWS_SECRET_ACCESS_KEY":"sensitive-cloud",
                "HF_TOKEN":"sensitive-model",
                "OPENAI_API_KEY":"sensitive-api",
                "MERLIN_MODEL_PATH":"/tmp/model.gguf",
                "PYTHONPATH":"/tmp/untrusted",
                "LD_LIBRARY_PATH":"/tmp/unsafe",
                "DYLD_LIBRARY_PATH":"/tmp/unsafe"}
        env=isolated_model_environment(source)
        self.assertEqual(env,{"PATH":"/usr/bin","LANG":"C","HOME":"/tmp"})
        for secret in ("sensitive-github","sensitive-gitlab","sensitive-ci",
                       "sensitive-cloud","sensitive-model","sensitive-api"):
            self.assertNotIn(secret,repr(env))

    def test_unknown_new_token_fails_closed(self):
        env=isolated_model_environment({"PATH":"/bin","FUTURE_PROVIDER_CREDENTIAL":"new"})
        self.assertEqual(env,{"PATH":"/bin"})

    def test_non_string_values_not_inherited(self):
        self.assertEqual(isolated_model_environment({"PATH":123,"LANG":"C"}),{"LANG":"C"})


if __name__=="__main__":
    unittest.main()
