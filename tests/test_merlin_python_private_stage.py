"""Adversarial, no-network tests for Merlin's pinned interpreter private staging."""
import gzip
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import tarfile
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('stage', Path(__file__).parents[1] / 'scripts' / 'merlin_python_private_stage.py')
S = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(S)
PYTHON = b'non-executable synthetic data only\n'


def build_archive(parts=None):
    if parts is None:
        parts = [('python/bin/python3.11', 'file', PYTHON, 0o755),
                 ('python/lib/python3.11/encodings/__init__.py', 'file', b'# plain text\n', 0o644),
                 ('python/bin/python3', 'symlink', 'python3.11', 0o777)]
    contents = io.BytesIO()
    with tarfile.open(fileobj=contents, mode='w', format=tarfile.PAX_FORMAT) as tf:
        for name, kind, raw, mode in parts:
            i = tarfile.TarInfo(name)
            i.mode = mode
            if kind == 'file':
                i.type = tarfile.REGTYPE
                i.size = len(raw)
                tf.addfile(i, io.BytesIO(raw))
            elif kind == 'symlink':
                i.type = tarfile.SYMTYPE
                i.linkname = raw
                tf.addfile(i)
            elif kind == 'hardlink':
                i.type = tarfile.LNKTYPE
                i.linkname = raw
                tf.addfile(i)
            elif kind == 'dir':
                i.type = tarfile.DIRTYPE
                tf.addfile(i)
            else:
                i.type = tarfile.CHRTYPE
                tf.addfile(i)
    return gzip.compress(contents.getvalue(), mtime=0)


class PrivateStageTests(unittest.TestCase):
    def assert_invalid(self, parts, reason):
        raw = build_archive(parts)
        with io.BytesIO(raw) as f, self.assertRaisesRegex(S.StageError, reason):
            S.inspect_archive(f, hashlib.sha256(PYTHON).hexdigest())

    def test_fixed_digest_and_size_fail_before_parse(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'archive.tar.gz'
            raw = build_archive()
            p.write_bytes(raw)
            with self.assertRaisesRegex(S.StageError, 'archive_size_or_type_differs'):
                S.fixed_archive(p, expected_sha256='0'*64, expected_bytes=len(raw)+1)
            with self.assertRaisesRegex(S.StageError, 'archive_hash_differs'):
                S.fixed_archive(p, expected_sha256='0'*64, expected_bytes=len(raw))

    def test_symlink_archive_input_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'a'; p.write_bytes(build_archive())
            link = Path(td) / 'link';link.symlink_to(p)
            with self.assertRaisesRegex(S.StageError, 'archive_symlink_forbidden'):
                S.fixed_archive(link, '0'*64, link.stat().st_size)

    def test_implicit_directories_and_good_relative_alias(self):
        with io.BytesIO(build_archive()) as f:
            entries, ns, total = S.inspect_archive(f, hashlib.sha256(PYTHON).hexdigest())
        self.assertIn('python', ns)
        self.assertTrue(ns['python']['inferred'])
        self.assertEqual(entries['python/bin/python3']['resolved_target'], 'python/bin/python3.11')
        self.assertEqual(total, len(PYTHON) + len(b'# plain text\n'))

    def test_duplicate_member_rejected(self):
        self.assert_invalid([('python/bin/python3.11','file',PYTHON,0o755)]*2, 'duplicate_archive_member')

    def test_non_directory_ancestor_rejected(self):
        self.assert_invalid([('python/bin','file',b'bad',0o644),
                             ('python/bin/python3.11','file',PYTHON,0o755)], 'non_directory_ancestor')

    def test_link_escapes_and_missing_targets(self):
        self.assert_invalid([('python/bin/python3.11','file',PYTHON,0o755),
                             ('python/bin/bad','symlink','../../../etc/shadow',0o777)], 'symlink_outside_python_root')
        self.assert_invalid([('python/bin/python3.11','file',PYTHON,0o755),
                             ('python/bin/bad','symlink','missing',0o777)], 'dangling_symlink')

    def test_symlink_chain_loop_rejected(self):
        self.assert_invalid([('python/bin/python3.11','file',PYTHON,0o755),
                             ('python/bin/a','symlink','b',0o777),
                             ('python/bin/b','symlink','a',0o777)], 'symlink_cycle_or_excessive_hops')

    def test_hardlink_special_setid_rejected(self):
        for entry, reason in [
            (('python/bin/x','hardlink','python/bin/python3.11',0o644),'hardlinks_forbidden'),
            (('python/bin/x','special','',0o644),'special_archive_member_forbidden'),
            (('python/bin/x','file',b'x',0o4755),'setid_member_forbidden')]:
            with self.subTest(reason=reason):
                self.assert_invalid([('python/bin/python3.11','file',PYTHON,0o755),entry],reason)

    def test_link_resolution_prevents_deceptive_symlink_parent_escape(self):
        self.assert_invalid([
            ('python/bin/python3.11','file',PYTHON,0o755),
            ('python/lib/x','file',b'x',0o644),
            ('python/bin/up','symlink','../lib',0o777),
            ('python/bin/bad','symlink','up/../../bin/python3.11',0o777),
        ], 'symlink_component_escaped_python_root')

    def test_partial_stage_exception_removes_only_new_private_leaf(self):
        if os.geteuid() == 0: self.skipTest('requires nonroot')
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)/'private';parent.mkdir(mode=0o700)
            raw=build_archive();p=Path(td)/'archive';p.write_bytes(raw)
            original=S.file_hash
            def interrupted(stream, expected_size, *, sink=None):
                if sink is not None:
                    sink.write(b'partial')
                    raise S.StageError('injected_failure_mid_write')
                return original(stream,expected_size,sink=sink)
            with mock.patch.object(S,'file_hash',side_effect=interrupted):
                with self.assertRaisesRegex(S.StageError,'injected_failure_mid_write'):
                    S.stage_archive(p,parent,
                        expected_archive_sha256=hashlib.sha256(raw).hexdigest(),
                        expected_archive_bytes=len(raw),
                        expected_python_sha256=hashlib.sha256(PYTHON).hexdigest())
            self.assertEqual(list(parent.iterdir()),[])

    def test_entrypoint_must_match_fixed_hash_and_executable(self):
        raw = build_archive()
        with io.BytesIO(raw) as f, self.assertRaisesRegex(S.StageError,'entrypoint_identity_differs'):
            S.inspect_archive(f, '0'*64)
        self.assert_invalid([('python/bin/python3.11','file',PYTHON,0o644)], 'entrypoint_identity_differs')

    def test_parent_must_be_private_0700_and_non_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'world';p.mkdir(mode=0o755)
            os.chmod(p,0o755)
            with self.assertRaisesRegex(S.StageError,'private_0700_parent_required'):
                S.private_parent(p)
            os.chmod(p,0o700)
            self.assertEqual(S.private_parent(p),p)
            link = Path(td) / 'alias';link.symlink_to(p)
            with self.assertRaisesRegex(S.StageError,'parent_symlink_forbidden'):
                S.private_parent(link)

    def test_stage_requires_nonroot_and_never_executes_candidate(self):
        if os.geteuid() == 0:
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(S.StageError,'nonroot_operation_required'):
                    S.stage_archive(Path(td)/'none',td)
            self.skipTest('full unprivileged staging tested under nonroot')
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)/'private';parent.mkdir(mode=0o700)
            raw=build_archive();p=Path(td)/'archive';p.write_bytes(raw)
            with mock.patch.object(S.os, 'system', side_effect=AssertionError('candidate execution forbidden')), \
                 mock.patch.object(S.os, 'execve', side_effect=AssertionError('candidate execution forbidden')):
                receipt=S.stage_archive(p,parent,
                    expected_archive_sha256=hashlib.sha256(raw).hexdigest(),
                    expected_archive_bytes=len(raw),
                    expected_python_sha256=hashlib.sha256(PYTHON).hexdigest())
            root=Path(receipt['staging_path'])
            self.assertEqual((root/'python/bin/python3.11').read_bytes(),PYTHON)
            self.assertEqual((root/'python/bin/python3').readlink().as_posix(),'python3.11')
            self.assertEqual(stat.S_IMODE((root/'python/bin/python3.11').stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE((root/'python/lib/python3.11/encodings/__init__.py').stat().st_mode),0o600)
            self.assertFalse(receipt['native_interpreter_executed'])
            self.assertFalse(receipt['python_startup_verified'])
            self.assertFalse(receipt['host_system_installation'])
            self.assertEqual(receipt['archive_members'],3)

    def test_no_staging_after_bad_archive_hash(self):
        if os.geteuid() == 0: self.skipTest('requires nonroot')
        with tempfile.TemporaryDirectory() as td:
            parent=Path(td)/'private';parent.mkdir(mode=0o700)
            p=Path(td)/'a';p.write_bytes(build_archive())
            with self.assertRaisesRegex(S.StageError,'archive_hash_differs'):
                S.stage_archive(p,parent,expected_archive_sha256='0'*64,
                                expected_archive_bytes=p.stat().st_size)
            self.assertFalse(list(parent.iterdir()))


if __name__=='__main__':
    unittest.main()
