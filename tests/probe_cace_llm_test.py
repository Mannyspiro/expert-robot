import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('probe', Path(__file__).resolve().parents[1] / 'scripts/probe_cace_llm.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
HEALTH = {'status': 'ok'}
MODELS = {'data': [{'id': p.MODEL}]}
CHAT = {'model': p.MODEL, 'choices': [{'message': {'role': 'assistant', 'content': 'Hello.'}}]}


class ProbeTests(unittest.TestCase):
    def run_probe(self, responses, infer=True):
        with patch.object(p, 'request_json', side_effect=responses) as request:
            result = p.probe(infer=infer)
        return result, request

    def test_cace_failure_does_not_hide_model_endpoint(self):
        result, request = self.run_probe([OSError(), MODELS])
        self.assertFalse(result['ok'])
        self.assertEqual(result['llm']['status'], 'ready')
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result['inference']['status'], 'blocked_by_health')

    def test_health_only_does_not_generate(self):
        result, request = self.run_probe([HEALTH, MODELS], infer=False)
        self.assertTrue(result['ok'])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(result['inference']['status'], 'not_requested')

    def test_realistic_response_is_observation_not_attestation(self):
        result, request = self.run_probe([HEALTH, MODELS, CHAT])
        self.assertTrue(result['ok'])
        self.assertEqual(result['inference']['status'], 'response_observed')
        self.assertFalse(result['formal_verified'])
        self.assertFalse(result['promotion_authority'])
        self.assertFalse(result['model_bytes_attested'])
        self.assertEqual(request.call_args.args[2]['max_tokens'], 32)

    def test_wrong_model_never_receives_inference(self):
        result, request = self.run_probe([HEALTH, {'data': [{'id': 'wrong'}]}])
        self.assertFalse(result['ok'])
        self.assertEqual(request.call_count, 2)

    def test_missing_model_empty_text_or_wrong_role_cannot_pass(self):
        for reply in [{}, {'choices': CHAT['choices']},
                      {'model': 'wrong', 'choices': CHAT['choices']},
                      {'model': p.MODEL, 'choices': [{'message': {'role': 'assistant', 'content': ''}}]},
                      {'model': p.MODEL, 'choices': [{'message': {'role': 'user', 'content': 'Hi'}}]}]:
            with self.subTest(reply=reply):
                result, _ = self.run_probe([HEALTH, MODELS, reply])
                self.assertFalse(result['ok'])

    def test_remote_endpoints_rejected(self):
        with self.assertRaises(ValueError):
            p.request_json('https://example.com/', 1)

    def test_redirects_rejected(self):
        self.assertIsNone(p.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_invalid_timeout_rejected(self):
        for value in [0, -1, 11, float('nan'), float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.probe(timeout=value)

    def test_invalid_or_oversized_json_rejected(self):
        for raw in [b'[]', b'broken', b'a' * (p.MAX_BYTES + 1)]:
            with patch.object(p, 'build_opener') as factory:
                factory.return_value.open.return_value = io.BytesIO(raw)
                with self.assertRaises(ValueError):
                    p.request_json(p.CACE, 1)


if __name__ == '__main__':
    unittest.main()
