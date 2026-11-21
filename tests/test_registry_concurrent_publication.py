"""Two canonical producers of identical content must not share a staging file."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from merlin.project_registry import MerlinRegistry


class RegistryPublicationTests(unittest.TestCase):
    def test_simultaneous_same_digest_writes_keep_one_version_and_no_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = MerlinRegistry(Path(directory) / 'registry')
            registry.register_project('project', 'Concurrent publication fixture')
            payload = b'Identical canonical evidence from two concurrent producers.'
            identity = hashlib.sha256(payload).hexdigest()
            target = registry.blobs / identity[:2] / identity[2:]
            barrier = threading.Barrier(2)
            real_replace = os.replace
            staging = []

            def simultaneous_replace(source, destination):
                if Path(destination) == target:
                    staging.append(str(source))
                    barrier.wait(timeout=5)
                return real_replace(source, destination)

            with patch('merlin.project_registry.os.replace', side_effect=simultaneous_replace):
                with ThreadPoolExecutor(max_workers=2) as workers:
                    futures = [workers.submit(registry.put_artifact, 'project', 'evidence.json', payload)
                               for _ in range(2)]
                    self.assertEqual([future.result(timeout=10) for future in futures], [identity, identity])
            self.assertEqual(len(set(staging)), 2)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(len(registry.artifact_history('project', 'evidence.json')), 1)
            self.assertTrue(registry.verify_artifact(identity))
            self.assertEqual(list(target.parent.glob('*.tmp')), [])

    def test_failed_publication_removes_only_owned_staging_file(self):
        with tempfile.TemporaryDirectory() as directory:
            registry = MerlinRegistry(Path(directory) / 'registry')
            registry.register_project('project', 'Failed publication fixture')
            payload = b'Failure before atomic publication.'
            identity = hashlib.sha256(payload).hexdigest()
            parent = registry.blobs / identity[:2]
            parent.mkdir()
            unrelated = parent / 'other-writer.tmp'
            unrelated.write_bytes(b'Unrelated in-flight writer')
            with patch('merlin.project_registry.os.replace', side_effect=OSError('fixture failure')):
                with self.assertRaises(OSError):
                    registry.put_artifact('project', 'failure.json', payload)
            self.assertEqual(unrelated.read_bytes(), b'Unrelated in-flight writer')
            self.assertEqual(list(parent.iterdir()), [unrelated])
            self.assertEqual(registry.artifact_history('project', 'failure.json'), [])


if __name__ == '__main__':
    unittest.main()
