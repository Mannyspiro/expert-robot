import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from merlin_research_browser import RetrievalDenied, retrieve


class ResearchBrowserTests(unittest.TestCase):
    def test_preserves_raw_bytes_and_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            result = retrieve('https://example.org/research', Path(folder), transport=lambda u, m, t: (u, 200, 'text/plain', b'original evidence'))
            self.assertEqual(Path(result.artifact).read_bytes(), b'original evidence')
            self.assertEqual(json.loads((Path(folder) / (result.sha256 + '.json')).read_text())['sha256'], result.sha256)

    def test_rejects_unsafe_schemes_and_credentials(self):
        for url in ('file:///etc/passwd', 'http://user:pass@example.org', 'http://127.0.0.1/private'):
            with self.assertRaises(RetrievalDenied):
                retrieve(url, Path('/tmp/unused'), transport=lambda u, m, t: (u, 200, 'text/plain', b'x'))

    def test_rejects_oversize(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RetrievalDenied):
                retrieve('https://example.org', Path(folder), max_bytes=2, transport=lambda u, m, t: (u, 200, 'text/plain', b'abc'))

    def test_rejects_private_redirect(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RetrievalDenied):
                retrieve('https://example.org', Path(folder), transport=lambda u, m, t: ('http://127.0.0.1', 200, 'text/plain', b'x'))


if __name__ == '__main__':
    unittest.main()
