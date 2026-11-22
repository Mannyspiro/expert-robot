#!/usr/bin/env python3
"""Inspect or privately stage one hash-pinned CPython build; never execute it.

Designed for an unprivileged, mode-0700 scratch directory. No network, sudo,
system directories, model inference, service lifecycle or import of archive code.
Stage copies archive entries to a new private leaf and verifies their bytes.
A successful stage is NOT a verified Python startup or host qualification.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import stat
import tarfile
import tempfile

SCHEMA = 'merlin-private-cpython-stage/1'
EXPECTED_ARCHIVE_SHA256 = '623a370be4489d8c35c7a274be02f3007a030618cda29025780beb416c6c8861'
EXPECTED_ARCHIVE_BYTES = 49_469_868
EXPECTED_PYTHON_SHA256 = '6cfad927461ace659b09716fad2efa828c6a4b084b7be8181c3982a9f36f464c'
ENTRYPOINT = 'python/bin/python3.11'
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_MEMBERS = 20_000
MAX_PATH_BYTES = 512
BUFFER = 1024 * 1024


class StageError(ValueError):
    """A fixed, non-sensitive failure explanation."""


def require(condition, message):
    if not condition:
        raise StageError(message)


def file_hash(stream, expected_size, *, sink=None):
    digest = hashlib.sha256()
    remaining = expected_size
    while remaining:
        chunk = stream.read(min(BUFFER, remaining))
        require(chunk, 'incomplete_member_bytes')
        digest.update(chunk)
        if sink is not None:
            sink.write(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def fixed_archive(path, expected_sha256=EXPECTED_ARCHIVE_SHA256,
                  expected_bytes=EXPECTED_ARCHIVE_BYTES):
    """Open one pinned existing regular file without following an archive symlink."""
    path = Path(path)
    require(not path.is_symlink(), 'archive_symlink_forbidden')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    f = os.fdopen(fd, 'rb')
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size == expected_bytes
                and expected_bytes <= MAX_ARCHIVE_BYTES, 'archive_size_or_type_differs')
        digest = file_hash(f, expected_bytes)
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) ==
                (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size),
                'archive_identity_changed')
        require(digest == expected_sha256, 'archive_hash_differs')
        f.seek(0)
        return f
    except BaseException:
        f.close()
        raise


def safe_name(name, *, directory=False):
    require(isinstance(name, str) and name and '\\' not in name and not name.startswith('/')
            and len(name.encode('utf-8')) <= MAX_PATH_BYTES
            and all(32 <= ord(c) < 127 or ord(c) >= 160 for c in name),
            'unsafe_archive_name')
    value = name.rstrip('/') if directory else name
    pieces = value.split('/')
    require(all(p not in ('', '.', '..') for p in pieces)
            and (value == 'python' or value.startswith('python/')),
            'archive_name_outside_python_root')
    return value


def safe_link(name, target):
    require(isinstance(target, str) and target and '\\' not in target
            and not target.startswith('/') and len(target.encode('utf-8')) <= MAX_PATH_BYTES
            and all(ord(c) >= 32 and ord(c) != 127 for c in target),
            'unsafe_symlink_value')
    lexical = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    require(lexical == 'python' or lexical.startswith('python/'), 'symlink_outside_python_root')
    return lexical


def directory_namespace(entries):
    ns = dict(entries)
    for name in entries:
        parent = posixpath.dirname(name)
        while parent:
            require(len(ns) <= MAX_MEMBERS * 2, 'namespace_size_ceiling')
            if parent not in ns:
                ns[parent] = {'type': 'directory', 'inferred': True}
            require(ns[parent]['type'] == 'directory', 'non_directory_ancestor')
            parent = posixpath.dirname(parent)
    require(ns.get('python', {}).get('type') == 'directory', 'python_root_directory_missing')
    return ns


def resolve_link(name, entries):
    # Walk path components in POSIX order: resolve symlinks before subsequent '..'.
    stack = posixpath.dirname(name).split('/')
    pending = entries[name]['target'].split('/')
    hops = 1
    while pending:
        part = pending.pop(0)
        if part == '':
            continue
        current = '/'.join(stack)
        require(entries.get(current, {}).get('type') == 'directory', 'symlink_parent_not_directory')
        if part == '.':
            continue
        if part == '..':
            require(len(stack) > 1, 'symlink_component_escaped_python_root')
            stack.pop()
            continue
        target = '/'.join(stack + [part])
        require(target in entries, 'dangling_symlink')
        record = entries[target]
        if record['type'] == 'symlink':
            hops += 1
            require(hops <= 64, 'symlink_cycle_or_excessive_hops')
            pending = record['target'].split('/') + pending
        else:
            stack.append(part)
            if pending:
                require(record['type'] == 'directory', 'symlink_traverses_file')
    return '/'.join(stack)


def inspect_archive(stream, expected_python_sha256=EXPECTED_PYTHON_SHA256):
    """A read-only independent member census, not a signature or a license review."""
    stream.seek(0)
    entries = {}
    total_bytes = 0
    with tarfile.open(fileobj=stream, mode='r:gz', errorlevel=2) as tf:
        for member in tf:
            require(len(entries) < MAX_MEMBERS, 'too_many_archive_members')
            name = safe_name(member.name, directory=member.isdir())
            require(name not in entries, 'duplicate_archive_member')
            require(not member.sparse and not any(k.startswith('GNU.sparse') for k in member.pax_headers),
                    'sparse_members_forbidden')
            require(not member.mode & 0o6000, 'setid_member_forbidden')
            require(not member.islnk(), 'hardlinks_forbidden')
            require(0 <= member.size <= MAX_FILE_BYTES, 'member_size_ceiling')
            if member.isdir():
                require(member.size == 0, 'directory_payload_forbidden')
                record = {'type': 'directory'}
            elif member.issym():
                require(member.size == 0, 'symlink_payload_forbidden')
                safe_link(name, member.linkname)
                record = {'type': 'symlink', 'target': member.linkname}
            elif member.isfile():
                total_bytes += member.size
                require(total_bytes <= MAX_UNCOMPRESSED_BYTES, 'archive_uncompressed_ceiling')
                payload = tf.extractfile(member)
                require(payload is not None, 'archive_file_unreadable')
                digest = file_hash(payload, member.size)
                require(not payload.read(1), 'member_trailing_bytes')
                record = {'type': 'file', 'bytes': member.size, 'sha256': digest,
                          'executable': bool(member.mode & 0o111)}
            else:
                raise StageError('special_archive_member_forbidden')
            entries[name] = record
    ns = directory_namespace(entries)
    for name, record in entries.items():
        if record['type'] == 'symlink':
            record['resolved_target'] = resolve_link(name, ns)
    main = entries.get(ENTRYPOINT, {})
    require(main.get('type') == 'file' and main.get('executable')
            and main.get('sha256') == expected_python_sha256, 'entrypoint_identity_differs')
    return entries, ns, total_bytes


def private_parent(parent):
    path = Path(parent)
    require(not path.is_symlink(), 'parent_symlink_forbidden')
    info = os.lstat(path)
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
            and stat.S_IMODE(info.st_mode) == 0o700, 'private_0700_parent_required')
    return path


def stage_archive(archive, parent, *, expected_archive_sha256=EXPECTED_ARCHIVE_SHA256,
                  expected_archive_bytes=EXPECTED_ARCHIVE_BYTES,
                  expected_python_sha256=EXPECTED_PYTHON_SHA256):
    """Atomically create a new private copy. Does not execute installed Python."""
    require(os.geteuid() != 0, 'nonroot_operation_required')
    parent = private_parent(parent)
    with fixed_archive(archive, expected_archive_sha256, expected_archive_bytes) as stream:
        entries, namespace, total = inspect_archive(stream, expected_python_sha256)
        root = Path(tempfile.mkdtemp(prefix='merlin-cpython-stage-', dir=str(parent)))
        created_stat = root.stat()
        try:
            # Create all directories before file payloads; no symlink parent exists yet.
            for name in sorted((n for n,v in namespace.items() if v['type'] == 'directory'),
                               key=lambda s: (s.count('/'),s)):
                path = root.joinpath(*name.split('/'))
                path.mkdir(mode=0o700, exist_ok=False)
                path.chmod(0o700)
            stream.seek(0)
            count = 0
            with tarfile.open(fileobj=stream, mode='r:gz', errorlevel=2) as tf:
                for member in tf:
                    name = safe_name(member.name, directory=member.isdir())
                    entry = entries[name]
                    if entry['type'] != 'file':
                        continue
                    out_path = root.joinpath(*name.split('/'))
                    mode = 0o700 if entry['executable'] else 0o600
                    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                 getattr(os, 'O_NOFOLLOW', 0), mode)
                    try:
                        with os.fdopen(fd, 'wb') as target:
                            payload = tf.extractfile(member)
                            require(payload is not None, 'staging_member_missing')
                            require(file_hash(payload, entry['bytes'], sink=target) == entry['sha256'],
                                    'staged_member_hash_differs')
                            target.flush()
                            os.fchmod(target.fileno(), mode)
                    except BaseException:
                        raise
                    count += 1
            for name in sorted((n for n,v in entries.items() if v['type'] == 'symlink')):
                record = entries[name]
                link_path = root.joinpath(*name.split('/'))
                os.symlink(record['target'], link_path)
                # This is a link identity check, not a permission/effect approval.
                require(os.readlink(link_path) == record['target'], 'symlink_changed_after_stage')
            receipt = {'schema': SCHEMA, 'archive_sha256': expected_archive_sha256,
                       'entrypoint_sha256': expected_python_sha256,
                       'archive_members': len(entries), 'staged_files': count,
                       'staged_total_file_bytes': total,
                       'directory_entries_including_inferred': sum(v['type'] == 'directory' for v in namespace.values()),
                       'symlink_entries': sum(v['type'] == 'symlink' for v in entries.values()),
                       'staging_path': str(root), 'staging_immutable': False,
                       'native_interpreter_executed': False, 'python_startup_verified': False,
                       'host_system_installation': False, 'service_mutations': False,
                       'production_qualified': False}
            receipt_path = root/'stage-receipt.json'
            with receipt_path.open('x', encoding='utf-8') as f:
                f.write(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
            os.chmod(receipt_path, 0o600)
            return receipt
        except BaseException:
            try:
                now = os.lstat(root)
                if (now.st_dev, now.st_ino) == (created_stat.st_dev, created_stat.st_ino):
                    shutil.rmtree(root)
            except OSError:
                pass
            raise


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True, help='Existing pinned archive; no download')
    ap.add_argument('--parent', type=Path, required=True, help='Existing UID-owned mode-0700 private parent')
    ap.add_argument('--stage', action='store_true', help='Create an unprivileged temporary stage (no execution)')
    ns = ap.parse_args(argv)
    try:
        if ns.stage:
            result = stage_archive(ns.archive, ns.parent)
        else:
            with fixed_archive(ns.archive) as s:
                entries, dirs, total = inspect_archive(s)
            result = {'schema': SCHEMA, 'archive_members': len(entries),
                      'namespace_entries': len(dirs), 'regular_file_bytes': total,
                      'staging_performed': False, 'native_interpreter_executed': False,
                      'production_qualified': False}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (StageError, OSError, tarfile.TarError, EOFError) as e:
        print(json.dumps({'schema': SCHEMA, 'status': 'blocked',
                          'error': str(e) if isinstance(e, StageError) else type(e).__name__,
                          'staging_performed': False, 'native_interpreter_executed': False}))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
