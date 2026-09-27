#!/usr/bin/env python3
"""Check CACE on THIS host; never install, start, or remotely expose a service."""
import argparse
from datetime import datetime, timezone
import json
import math
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

MODEL = 'Qwen/Qwen3.5-4B'
CACE = 'http://127.0.0.1:8765/api/health'
MODELS = 'http://127.0.0.1:8080/v1/models'
CHAT = 'http://127.0.0.1:8080/v1/chat/completions'
MAX_BYTES = 65536


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, timeout, payload=None):
    if url not in (CACE, MODELS, CHAT):
        raise ValueError('only fixed local endpoints are permitted')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    body = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=body, headers={'Accept': 'application/json',
                                         'Content-Type': 'application/json'})
    with opener.open(req, timeout=timeout) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('response exceeds diagnostic byte limit')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('response must be a JSON object')
    return value


def probe(infer=False, timeout=3.0):
    if not math.isfinite(timeout) or not 0 < timeout <= 10:
        raise ValueError('timeout must be finite and in (0, 10] seconds')
    result = {'schema_version': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
              'scope': 'current_execution_host_only', 'expected_model': MODEL,
              'cace': {}, 'llm': {}, 'inference': {'status': 'not_requested'},
              'formal_verified': False, 'promotion_authority': False,
              'model_bytes_attested': False}
    # Independent checks: CACE failure must not hide whether the LLM responds.
    for name, url in [('cace', CACE), ('llm', MODELS)]:
        try:
            payload = request_json(url, timeout)
            if name == 'cace':
                ready = payload.get('status') == 'ok'
                result[name] = {'endpoint': url, 'status': 'ready' if ready else 'unhealthy'}
            else:
                data = payload.get('data', [])
                if not isinstance(data, list):
                    raise ValueError('model list must be an array')
                ids = [x['id'] for x in data if isinstance(x, dict) and isinstance(x.get('id'), str)]
                result[name] = {'endpoint': url, 'status': 'ready' if MODEL in ids else 'model_mismatch',
                                'model_ids': ids[:20]}
        except Exception as error:
            result[name] = {'endpoint': url, 'status': 'unavailable',
                            'error_type': type(error).__name__}
    healthy = all(result[name]['status'] == 'ready' for name in ('cace', 'llm'))
    if infer:
        result['inference'] = {'status': 'blocked_by_health'}
        if healthy:
            try:
                payload = request_json(CHAT, timeout, {
                    'model': MODEL, 'messages': [{'role': 'user', 'content': 'Reply with one brief greeting.'}],
                    'max_tokens': 32, 'temperature': 0, 'stream': False})
                if payload.get('model') != MODEL:
                    raise ValueError('inference model identity missing or mismatched')
                message = payload['choices'][0]['message']
                content = message.get('content')
                if message.get('role') != 'assistant' or not isinstance(content, str) or not content.strip():
                    raise ValueError('inference must return nonempty assistant text')
                result['inference'] = {'status': 'response_observed', 'model': MODEL,
                                       'text_preview': content[:256], 'untrusted': True}
            except Exception as error:
                result['inference'] = {'status': 'failed', 'error_type': type(error).__name__}
    result['ok'] = healthy and (not infer or result['inference']['status'] == 'response_observed')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--infer', action='store_true', help='request at most 32 output tokens after both health checks pass')
    parser.add_argument('--timeout', type=float, default=3.0, help='per-operation socket timeout, at most 10 seconds')
    args = parser.parse_args()
    result = probe(args.infer, args.timeout)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
