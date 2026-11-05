import unittest
from unittest.mock import patch
import json
from github_commit_receipt import fetch_commit
class Response:
 status=200
 def __enter__(self): return self
 def __exit__(self,*a): pass
 def read(self,n): return json.dumps({"sha":"a"*40,"html_url":"https://github.com/o/r/commit/"+"a"*40,"commit":{"verification":{"verified":True,"reason":"valid"},"author":{"date":"2026-01-01T00:00:00Z"},"committer":{"date":"2026-01-01T00:00:00Z"}}}).encode()
class GithubReceiptTests(unittest.TestCase):
 @patch("github_commit_receipt.urllib.request.urlopen",return_value=Response())
 def test_receipt_uses_api_canonical_sha(self,mock):
  r=fetch_commit("o/r","a"*40)
  self.assertTrue(r["signature_verified"])
  self.assertEqual(r["canonical_sha"],"a"*40)
if __name__=="__main__": unittest.main()
