#!/usr/bin/env python3
"""Explicit preparation only: fetch locked artifacts; never launch a model."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(item, directory):
    target = directory / item['filename']
    if target.is_file() and target.stat().st_size == item['size'] and digest(target) == item['sha256']:
        return target
    temporary = target.with_suffix('.part')
    start = time.monotonic()
    try:
        with urllib.request.urlopen(item['url'], timeout=30) as response, temporary.open('wb') as output:
            size = 0
            while chunk := response.read(1024 * 1024):
                size += len(chunk)
                if size > item['size'] or time.monotonic() - start > 300:
                    raise ValueError('download size/time limit exceeded')
                output.write(chunk)
        if size != item['size'] or digest(temporary) != item['sha256']:
            raise ValueError('artifact checksum or size mismatch')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise SystemExit('This release lock is Linux x86_64 only; qualify another runtime for ARM64/macOS.')
    lock = json.loads((ROOT / 'config/cace_recovery_artifacts.json').read_text())
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(directory).free < 2_000_000_000:
        raise SystemExit('At least 2 GB free space required')
    model = download(lock['model'], directory)
    archive = download(lock['runtime'], directory)
    # A fresh extraction avoids accepting stale libraries from an older runtime.
    import tempfile
    runtime = Path(tempfile.mkdtemp(prefix='runtime-b11146-', dir=directory))
    with tarfile.open(archive) as source:
        source.extractall(runtime, filter='data')
    server = runtime / lock['runtime']['server_relative_path']
    if digest(server) != lock['runtime']['server_sha256']:
        raise SystemExit('extracted server digest mismatch')
    print(json.dumps({'model': str(model), 'server': str(server),
                      'model_sha256': lock['model']['sha256'],
                      'server_sha256': lock['runtime']['server_sha256']}, indent=2))


if __name__ == '__main__':
    main()
