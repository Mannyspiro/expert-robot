#!/usr/bin/env python3
"""Offline real inference smoke; starts and stops its own loopback CPU server."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from cace_headless import CACEHeadlessClient, HeadlessConfig


def verify(path, expected):
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
            raise ValueError('artifact digest mismatch: ' + path.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    lock = json.loads((ROOT / 'config/cace_recovery_artifacts.json').read_text())
    verify(args.model, lock['model']['sha256'])
    verify(args.server, lock['runtime']['server_sha256'])
    config = HeadlessConfig.load(ROOT / 'config/cace_headless_local.json')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = 'http://127.0.0.1:' + str(port) + '/v1'
    opener = build_opener(ProxyHandler({}))
    cases = [('Reply with only the integer result of 2 + 3.', '5'),
             ('Reply with only the next integer: 2, 4, 6, 8,', '10')]
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen([str(args.server.resolve()), '-m', str(args.model.resolve()),
            '--host', '127.0.0.1', '--port', str(port), '--alias', config.model_id,
            '-c', '2048', '-t', '4', '-ngl', '0'], stdout=log, stderr=subprocess.STDOUT)
        try:
            ready = False
            for _ in range(100):
                if proc.poll() is not None:
                    raise RuntimeError('server exited before readiness')
                try:
                    with opener.open(url + '/models', timeout=1) as response:
                        models = json.load(response)
                    ready = any(row.get('id') == config.model_id for row in models.get('data', []))
                    if ready:
                        break
                except OSError:
                    pass
                time.sleep(.2)
            if not ready:
                raise RuntimeError('local model did not become ready')
            client = CACEHeadlessClient(replace(config, llm_base_url=url), timeout=20)
            results = []
            for prompt, expected in cases:
                start = time.monotonic()
                answer = client.chat([{'role': 'user', 'content': prompt}], temperature=0, max_tokens=32)
                results.append({'prompt': prompt, 'expected': expected, 'response': answer,
                                'exact_match': answer['text'].strip() == expected,
                                'elapsed_seconds': round(time.monotonic() - start, 3)})
            evidence = {'schema_version': 1, 'observed_at': datetime.now(timezone.utc).isoformat(),
                        'scope': 'local_cpu_development_smoke_only', 'model': config.model_id,
                        'artifact_lock': lock, 'cases': results,
                        'all_exact_matches': all(row['exact_match'] for row in results),
                        'cace_api_verified': False, 'formal_verified': False,
                        'promotion_authority': False, 'hidden_evaluation': False}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, indent=2) + '\n')
            print(json.dumps({'output': str(args.output), 'cases': results,
                              'all_exact_matches': evidence['all_exact_matches']}, indent=2))
            return 0 if evidence['all_exact_matches'] else 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


if __name__ == '__main__':
    raise SystemExit(main())
