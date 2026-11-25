"""Focused configuration rejection tests; synthetic identities, no network calls."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("merlin_deployment_config", ROOT / "check_config.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


def fixture():
    # These are parser fixtures only, not deployed account/domain identities.
    gateway = {
        "schema": "merlin-studio-trusted-gateway/1", "contract_version": 1,
        "public_origin": "https://merlin.validation-fixture.net",
        "team_name": "merlin-validation-fixture", "audiences": ["ab" * 32],
        "identity_verifier": "cloudflared-access-required",
    }
    tunnel = {
        "tunnel": "12345678-1234-4abc-8def-1234567890ab",
        "credentials-file": "/etc/merlin-studio-tunnel/credentials.json",
        "metrics": "127.0.0.1:20241",
        "ingress": [
            {"hostname": "merlin.validation-fixture.net", "service": "http://127.0.0.1:8771",
             "originRequest": {"httpHostHeader": "merlin.validation-fixture.net",
                               "access": {"required": True, "teamName": gateway["team_name"],
                                          "audTag": list(gateway["audiences"])}}},
            {"service": "http_status:404"},
        ],
    }
    return gateway, tunnel


class ConfigurationTests(unittest.TestCase):
    def test_services_hide_known_ci_runner_tree(self):
        for name in ("merlin-studio.service", "cloudflared-merlin.service"):
            with self.subTest(unit=name):
                lines = (ROOT / name).read_text().splitlines()
                inaccessible = [path for line in lines if line.startswith("InaccessiblePaths=")
                                for path in line.partition("=")[2].split()]
                self.assertIn("-/opt/actions-runner", inaccessible)
                self.assertIn("ProtectHome=yes", lines)

    def test_exact_protected_profile(self):
        CHECK.validate(*fixture())

    def test_origin_and_contract_negatives(self):
        changes = [
            ("public_origin", "http://merlin.validation-fixture.net"),
            ("public_origin", "https://merlin.validation-fixture.net/"),
            ("public_origin", "https://merlin.validation-fixture.net:443"),
            ("public_origin", "https://merlin.validation-fixture.net?x=1"),
            ("public_origin", "https://merlin.validation-fixture.net#x"),
            ("public_origin", "https://user@merlin.validation-fixture.net"),
            ("public_origin", "https://*.validation-fixture.net"),
            ("public_origin", "https://127.0.0.1"),
            ("public_origin", "https://merlin.example"),
            ("public_origin", "https://REPLACE_WITH_APPROVED_HOSTNAME"),
            ("identity_verifier", "header-present"),
            ("contract_version", True),
            ("audiences", []),
            ("audiences", ["ab" * 32, "ab" * 32]),
            ("audiences", ["REPLACE_WITH_ACCESS_APPLICATION_AUD"]),
            ("team_name", "untrusted.example/redirect"),
        ]
        for key, value in changes:
            with self.subTest(field=key, value=value):
                gateway, tunnel = fixture()
                gateway[key] = value
                with self.assertRaises((ValueError, TypeError)):
                    CHECK.validate(gateway, tunnel)

    def test_verifier_and_route_negatives(self):
        gateway, original = fixture()
        mutations = []
        for key, value in [("required", False), ("required", 1),
                           ("teamName", "other-team"), ("audTag", ["cd" * 32])]:
            changed = deepcopy(original)
            changed["ingress"][0]["originRequest"]["access"][key] = value
            mutations.append(changed)
        for target in ["http://0.0.0.0:8771", "http://127.0.0.1:8772", "http://other-host:8771"]:
            changed = deepcopy(original)
            changed["ingress"][0]["service"] = target
            mutations.append(changed)
        changed = deepcopy(original)
        changed["ingress"][0]["originRequest"]["httpHostHeader"] = "localhost:8771"
        mutations.append(changed)
        changed = deepcopy(original)
        changed["originRequest"] = {"access": changed["ingress"][0]["originRequest"].pop("access")}
        mutations.append(changed)
        changed = deepcopy(original)
        changed["ingress"].insert(1, {"hostname": "other.validation-fixture.net", "service": "http://127.0.0.1:8771"})
        mutations.append(changed)
        changed = deepcopy(original)
        changed["ingress"][0]["path"] = "/studio/.*"
        mutations.append(changed)
        changed = deepcopy(original)
        changed["ingress"][-1]["service"] = "http://127.0.0.1:8771"
        mutations.append(changed)
        changed = deepcopy(original)
        changed["metrics"] = "0.0.0.0:20241"
        mutations.append(changed)
        changed = deepcopy(original)
        changed["credentials-file"] = "/home/runner/credential.json"
        mutations.append(changed)
        changed = deepcopy(original)
        changed["tunnel"] = "00000000-0000-0000-0000-000000000000"
        mutations.append(changed)
        for index, tunnel in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises((ValueError, TypeError)):
                CHECK.validate(gateway, tunnel)

    def test_templates_cannot_be_started_unchanged(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "check_config.py"),
             "--gateway", str(ROOT / "gateway.json.example"),
             "--tunnel", str(ROOT / "cloudflared.yml.example")],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Deployment configuration rejected", result.stderr)
        self.assertNotIn("REPLACE_WITH_", result.stderr)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"required":true,"required":false}', object_pairs_hook=CHECK.unique_object)

    def test_unsafe_file_shape_and_permissions_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gateway.json"
            path.write_text(json.dumps(fixture()[0]))
            path.chmod(0o666)
            with self.assertRaises(ValueError):
                CHECK.load(path)
            path.chmod(0o600)
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                CHECK.load(link)
            with self.assertRaises(ValueError):
                CHECK.load(Path(directory))
            if os.geteuid() == 0:
                CHECK.load(path)
                os.chown(path, 65534, -1)
                with self.assertRaises(ValueError):
                    CHECK.load(path)


if __name__ == "__main__":
    unittest.main()
