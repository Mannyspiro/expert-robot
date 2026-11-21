"""Disposable proof of deterministic packaging, exclusion, and extraction startup."""
from pathlib import Path
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

REPO = Path('/workspace/scratch/e6b5ba62b1d9/expert-robot')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('portable_builder', REPO / 'portable/build_portable.py')
verifier = load('portable_verifier', REPO / 'scripts/verify_portable.py')
payload, origins = builder.collect_sources()
checks = []


def serve(command, state, native=False):
    environment = {**os.environ, 'MERLIN_MODEL_URL': '', 'MERLIN_MODEL_ID': '',
                   'BROWSER': shutil.which('true') or 'true'}
    proc = subprocess.Popen(command + ['--port', '0', '--data-dir', str(state)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=environment)
    try:
        line = proc.stdout.readline()
        match = re.search(r'http://127\.0\.0\.1:\d+', line)
        if not match:
            raise AssertionError('No startup address: ' + line)
        data = json.load(urllib.request.urlopen(match.group(0) + '/api/status', timeout=5))
        assert data['ready'] and not data['model']['configured'] and data['offline_commands']
        if native:
            assert data['core_runtime']['available'] and data['core_runtime']['healthy'], data['core_runtime']
    finally:
        proc.terminate()
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()


with tempfile.TemporaryDirectory(prefix='merlin-package-proof-') as folder:
    test = Path(folder)
    fixture = test / 'repo'
    fixture.mkdir()
    for name, origin in origins.items():
        target = fixture / origin
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload[name])
    canaries = [
        'portable/merlin_studio/data/registry/private.sqlite3',
        'portable/merlin_studio/workspace/private.txt',
        'portable/merlin_studio/__pycache__/private.pyc',
        'portable/merlin_studio/.env',
        'portable/merlin_studio/models/private.gguf',
        'portable/merlin_studio/bin/llama-server',
        'portable/merlin_studio/runtime/python/bin/python3',
        'portable/merlin_studio/credentials.json',
        'python/merlin/secrets.json',
    ]
    for relative in canaries:
        target = fixture / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('MERLIN_PACKAGING_PRIVATE_CANARY')
    builder.REPO = fixture
    first = builder.build(test / 'source-a.zip')
    second = builder.build(test / 'source-b.zip')
    assert first['sha256'] == second['sha256']
    checks.append('source ZIP deterministic across two builds')
    assert verifier.verify(test / 'source-a.zip')['verified']
    checks.append('source ZIP complete inventory/hash/mode verification')
    with zipfile.ZipFile(test / 'source-a.zip') as archive:
        names = archive.namelist()
        assert all(archive.getinfo(n).date_time == (1980, 1, 1, 0, 0, 0) for n in names)
        assert not any(b'MERLIN_PACKAGING_PRIVATE_CANARY' in archive.read(n) for n in names)
        assert not any('/data/' in n or '/workspace/' in n or '/__pycache__/' in n
                       or n.endswith(('.gguf', '.env', 'credentials.json')) for n in names)
        archive.extractall(test / 'source')
    checks.append('nine state/cache/credential/model/runtime canaries excluded')
    extracted = test / 'source' / builder.ARCHIVE_ROOT
    assert verifier.verify(extracted)['verified']
    checks.append('extracted package verification')
    serve(['python3', str(extracted / 'server.py')], test / 'state-source')
    checks.append('extracted source package starts with canonical registry and offline commands')
    serve(['sh', str(extracted / 'START.sh')], test / 'state-launcher')
    checks.append('Unix launcher starts extracted app using installed Python; browser opening suppressed for this check')
    (extracted / 'server.py').write_bytes((extracted / 'server.py').read_bytes() + b'\n# changed\n')
    try:
        verifier.verify(extracted)
    except ValueError:
        checks.append('changed extracted application rejected')
    else:
        raise AssertionError('tamper accepted')
    native = builder.build(test / 'native-a.zip', True)
    native_again = builder.build(test / 'native-b.zip', True)
    assert native['sha256'] == native_again['sha256']
    checks.append('native ZIP deterministic with same C++20 compiler and source')
    verified = verifier.verify(test / 'native-a.zip')
    assert verified['verified'] and verified['native_protocol']['platform'] == 'linux-x86_64'
    checks.append('native protocol compiled; two reference checks passed; full ZIP verified')
    with zipfile.ZipFile(test / 'native-a.zip') as archive:
        assert builder.ARCHIVE_ROOT + '/bin/expert_robot_runtime' in archive.namelist()
        assert builder.ARCHIVE_ROOT + '/bin/llama-server' not in archive.namelist()
        archive.extractall(test / 'native')
        # Python's extractall ignores Unix permissions; restore those verified in ZIP.
        for entry in archive.infolist():
            (test / 'native' / entry.filename).chmod((entry.external_attr >> 16) & 0o777)
    native_root = test / 'native' / builder.ARCHIVE_ROOT
    serve(['python3', str(native_root / 'server.py')], test / 'state-native', native=True)
    checks.append('extracted Linux x86_64 package starts and independently checks its protocol core')
    result = {'scope': 'disposable source and Linux x86_64 protocol-package validation; no final release ZIP retained',
              'checks': checks, 'source_file_count': first['files'],
              'source_zip_bytes': first['bytes'], 'source_zip_sha256': first['sha256'],
              'native_file_count': native['files'], 'native_zip_bytes': native['bytes'],
              'native_zip_sha256': native['sha256'], 'native_protocol': native['native_protocol'],
              'excluded_canary_count': len(canaries)}
    Path('/workspace/scratch/e6b5ba62b1d9/ui-qa/packaging-result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
