"""Negative mount-identity tests for the real OpenSandbox Docker acceptance."""
from pathlib import Path
import sys
import unittest
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "merlin"))
from native_sandbox_acceptance import validate_runtime_mounts


def fixture():
    return {
        "label_sandbox_id": "merlin-fixture-1",
        "binds": ["opensandbox-runtime-merlin-fixture-1:/opt/opensandbox:rw"],
        "mounts": [{"type": "volume", "name": "opensandbox-runtime-merlin-fixture-1",
                    "destination": "/opt/opensandbox", "rw": True}],
    }


class NativeRuntimeMountTests(unittest.TestCase):
    def test_only_pinned_sandbox_runtime_volume_is_accepted(self):
        self.assertEqual(validate_runtime_mounts(fixture()), "opensandbox-runtime-merlin-fixture-1")

    def test_any_real_host_path_is_rejected(self):
        value = fixture()
        value["binds"].append("/var/run/docker.sock:/var/run/docker.sock:rw")
        with self.assertRaises(AssertionError):
            validate_runtime_mounts(value)

    def test_wrong_runtime_owner_is_rejected(self):
        value = fixture()
        value["label_sandbox_id"] = "another-sandbox"
        with self.assertRaises(AssertionError):
            validate_runtime_mounts(value)

    def test_unexpected_mount_source_type_is_rejected(self):
        value = fixture()
        value["mounts"][0]["type"] = "bind"
        with self.assertRaises(AssertionError):
            validate_runtime_mounts(value)

    def test_read_only_volume_or_extra_volume_is_rejected(self):
        value = fixture()
        value["mounts"][0]["rw"] = False
        with self.assertRaises(AssertionError):
            validate_runtime_mounts(value)
        value = fixture()
        value["mounts"].append(deepcopy(value["mounts"][0]))
        with self.assertRaises(AssertionError):
            validate_runtime_mounts(value)


if __name__ == "__main__":
    unittest.main()
