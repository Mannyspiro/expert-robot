"""Read-only private status integration; all host/model observations are synthetic.

Compose the existing WeightBindingTests fixture explicitly rather than inheriting
its tests. Only this module's independent dispatcher controls are collected.
Unix transport is separate; these tests call the actual authorized dispatcher.
"""
from copy import copy, deepcopy
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from dot_ai_os.bridge import DotContextBridge, canonical, digest
from dot_ai_os.dual_coder import DualCoderWorkflow
from dot_ai_os.private_runtime import (
    PrivateDispatcher, PrivateHostConfigurationError, PrivateReadOnlyRegistry,
    RegisteredTool, load_configuration, main,
)
from merlin.weight_binding import WeightBinding
import test_weight_binding as fixtures


_DEFAULT = object()


def _file_identity(root):
    return {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


class PrivateWeightStatusTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.WeightBindingTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        writer = DotContextBridge(self.fixture.registry, project_id="test", namespaces=("rsi",))
        context = writer.ingest(namespace="rsi", source_id="private-status-fixture",
            title="Synthetic private status context",
            content=b"Synthetic engineering context; no model runtime.",
            source_url="https://example.invalid/private-status-fixture", source_version="fixture-v1",
            epistemic="local_observation", captured_at="2026-11-21T00:00:00Z")
        self.fixture.specification["context_refs"] = [context["source_ref"]]
        self.result = self.fixture.run_workflow("bound")
        self.assertEqual(self.result["status"], "completed_research_only")
        self.expected_provider_calls = dict(self.fixture.calls)
        self.reader = PrivateReadOnlyRegistry(self.fixture.registry.root)
        self.resolved = []
        self.fixture.authenticated.clear()

    def tearDown(self):
        self.assertEqual(self.fixture.calls, self.expected_provider_calls,
                         "status must not invoke any fixture provider")

    def binding(self, *, reader=None, authenticate=None, manifest_ref=None):
        return WeightBinding(self.reader if reader is None else reader, project_id="test",
            manifest_ref=self.fixture.manifest_ref if manifest_ref is None else manifest_ref,
            authenticate=self.fixture.authenticate if authenticate is None else authenticate)

    def dispatcher(self, *, reader=None, resolver=_DEFAULT, namespaces=("rsi",), grants=None):
        reader = self.reader if reader is None else reader
        if resolver is _DEFAULT:
            def resolver(session):
                self.resolved.append(session)
                return self.binding(reader=reader)
        return PrivateDispatcher(DotContextBridge(reader, project_id="test", namespaces=namespaces),
            grants={os.geteuid(): {"principal": "synthetic-reader", "tools": ["rsi_status"]}}
                if grants is None else grants,
            rsi_weight_binding_resolver=resolver)

    def call(self, dispatcher, *, session="bound", uid=None, tool="rsi_status", arguments=None):
        return dispatcher.call(os.geteuid() if uid is None else uid,
            {"schema": "merlin-private-call/1", "request_id": "status",
             "tool": tool, "arguments": {"session_id": session} if arguments is None else arguments})

    def assert_error(self, reply, code):
        self.assertEqual(reply, {"schema": "merlin-private-reply/1", "request_id": "status",
            "ok": False, "qualification": False, "promotion_authority": False,
            "error": {"code": code}})
        self.assertLess(len(canonical(reply)), 256)

    def test_bound_dispatcher_status_reauthenticates_without_provider_or_registry_writes(self):
        before = _file_identity(self.reader.root)
        with patch.object(DualCoderWorkflow, "run", side_effect=AssertionError("status cannot run providers")):
            reply = self.call(self.dispatcher())
        self.assertIs(reply["ok"], True)
        status = reply["result"]
        self.assertEqual(status["schema"], "dot-dual-coder-status/2")
        self.assertEqual(status["status"], "completed_research_only")
        self.assertEqual(status["weight_receipt_refs"]["coder_a"], self.result["coder_a_weight_receipt_ref"])
        self.assertEqual(self.resolved, ["bound"])
        self.assertEqual(len(self.fixture.authenticated), 1)
        for name in fixtures.FLAGS:
            self.assertIs(status[name], False)
        self.assertEqual(_file_identity(self.reader.root), before)

    def test_fresh_read_only_registry_restart_reauthenticates_every_status(self):
        first = self.call(self.dispatcher())
        reader = PrivateReadOnlyRegistry(self.reader.root)
        self.assertIsNot(reader, self.reader)
        before = _file_identity(reader.root)
        second = self.call(self.dispatcher(reader=reader))
        self.assertEqual(second, first)
        self.assertEqual(len(self.fixture.authenticated), 2)
        self.assertEqual(self.resolved, ["bound", "bound"])
        self.assertEqual(_file_identity(reader.root), before)

    def test_missing_resolver_is_explicit_and_never_unbound_fallback(self):
        self.assert_error(self.call(self.dispatcher(resolver=None)), "weight_binding_not_configured")
        self.assertEqual(self.fixture.authenticated, [])

    def test_resolver_returning_none_is_explicit(self):
        calls = []
        def missing(session):
            calls.append(session)
            return None
        self.assert_error(self.call(self.dispatcher(resolver=missing)), "weight_binding_not_configured")
        self.assertEqual(calls, ["bound"])

    def test_noncallable_resolver_configuration_is_rejected(self):
        for value in (False, 1, "module.callback", {"manifest": "caller-chosen"}):
            with self.subTest(value=value), self.assertRaises(PrivateHostConfigurationError):
                self.dispatcher(resolver=value)

    def test_resolver_must_return_a_weight_binding(self):
        for value in (True, 1, "binding", {"manifest_ref": self.fixture.manifest_ref}):
            with self.subTest(value=value):
                self.assert_error(self.call(self.dispatcher(resolver=lambda session: value)),
                                  "invalid_or_unavailable_arguments")
        self.assertEqual(self.fixture.authenticated, [])

    def test_binding_from_different_registry_object_is_rejected_even_same_root(self):
        other = PrivateReadOnlyRegistry(self.reader.root)
        binding = self.binding(reader=other)
        self.assertEqual(other.root, self.reader.root)
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)),
                          "invalid_or_unavailable_arguments")
        self.assertEqual(self.fixture.authenticated, [])

    def test_binding_with_wrong_project_is_rejected(self):
        binding = copy(self.binding())
        binding.project_id = "different-host-project"
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)),
                          "invalid_or_unavailable_arguments")
        self.assertEqual(self.fixture.authenticated, [])

    def test_revoked_host_authentication_blocks_next_status(self):
        dispatcher = self.dispatcher()
        self.assertIs(self.call(dispatcher)["ok"], True)
        self.fixture.allowed = False
        self.assert_error(self.call(dispatcher), "operation_not_permitted")
        self.assertEqual(len(self.fixture.authenticated), 2)

    def test_resolver_revoking_uid_grant_blocks_current_status_egress(self):
        dispatcher = self.dispatcher()
        def revoke(session):
            dispatcher.grants.pop(os.geteuid())
            return self.binding()
        dispatcher.rsi_weight_binding_resolver = revoke
        self.assert_error(self.call(dispatcher), "operation_not_permitted")

    def test_resolver_changing_principal_blocks_current_status_egress(self):
        dispatcher = self.dispatcher()
        def revoke(session):
            dispatcher.grants[os.geteuid()]["principal"] = "different-principal"
            return self.binding()
        dispatcher.rsi_weight_binding_resolver = revoke
        self.assert_error(self.call(dispatcher), "operation_not_permitted")

    def test_resolver_changing_tool_grant_blocks_current_status_egress(self):
        for tools in (("health",), ("rsi_status", "health")):
            with self.subTest(tools=tools):
                dispatcher = self.dispatcher()
                def revoke(session):
                    dispatcher.grants[os.geteuid()]["tools"] = tools
                    return self.binding()
                dispatcher.rsi_weight_binding_resolver = revoke
                self.assert_error(self.call(dispatcher), "operation_not_permitted")

    def test_resolver_revoking_context_scope_blocks_before_receipt_authentication(self):
        dispatcher = self.dispatcher()
        def revoke(session):
            dispatcher.bridge.namespaces = ("merlin",)
            return self.binding()
        dispatcher.rsi_weight_binding_resolver = revoke
        self.assert_error(self.call(dispatcher), "invalid_or_unavailable_arguments")
        self.assertEqual(self.fixture.authenticated, [])

    def test_authenticator_revoking_context_scope_blocks_status_egress(self):
        dispatcher = self.dispatcher()
        calls = []
        def revoke(receipt, checksum):
            calls.append(checksum)
            dispatcher.bridge.namespaces = ("merlin",)
            return True
        dispatcher.rsi_weight_binding_resolver = lambda session: self.binding(authenticate=revoke)
        self.assert_error(self.call(dispatcher), "invalid_or_unavailable_arguments")
        self.assertEqual(len(calls), 1)

    def test_authenticator_revoking_uid_grant_blocks_status_egress(self):
        dispatcher = self.dispatcher()
        calls = []
        def revoke(receipt, checksum):
            calls.append(checksum)
            dispatcher.grants.pop(os.geteuid())
            return True
        dispatcher.rsi_weight_binding_resolver = lambda session: self.binding(authenticate=revoke)
        self.assert_error(self.call(dispatcher), "operation_not_permitted")
        self.assertEqual(len(calls), 1)

    def test_status_egress_grant_check_does_not_change_other_plugin_semantics(self):
        bridge = DotContextBridge(self.reader, project_id="test", namespaces=("rsi",))
        def plugin(arguments, principal):
            dispatcher.grants[os.geteuid()]["principal"] = "changed-by-synthetic-plugin"
            return {"completed": True}
        dispatcher = PrivateDispatcher(bridge,
            grants={os.geteuid(): {"principal": "synthetic-reader", "tools": ["fixture_plugin"]}},
            plugin_tools={"fixture_plugin": RegisteredTool(plugin, frozenset())})
        reply = self.call(dispatcher, tool="fixture_plugin", arguments={})
        self.assertIs(reply["ok"], True)
        self.assertEqual(reply["result"], {"completed": True})

    def test_false_and_truthy_nonboolean_authentication_are_rejected(self):
        for value in (False, 1, "yes", {"verified": True}, None):
            with self.subTest(value=value):
                binding = self.binding(authenticate=lambda receipt, checksum: value)
                self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)),
                                  "operation_not_permitted")

    def test_authenticator_receives_exact_detached_receipt_and_digest(self):
        stored, _ = self.fixture.read("dual-coder/bound/stages/coder_a/weight-receipt.json")
        authenticated = []
        def authenticate(receipt, checksum):
            self.assertEqual(receipt, stored)
            self.assertEqual(checksum, digest(canonical(stored)))
            authenticated.append(checksum)
            receipt["payload"]["candidate"] = "detached callback mutation"
            return True
        before = _file_identity(self.reader.root)
        binding = self.binding(authenticate=authenticate)
        self.assertIs(self.call(self.dispatcher(resolver=lambda session: binding))["ok"], True)
        self.assertEqual(len(authenticated), 1)
        self.assertEqual(_file_identity(self.reader.root), before)

    def test_changed_manifest_selection_is_rejected(self):
        changed = deepcopy(self.fixture.manifest)
        changed["runtime"]["implementation_sha256"] = "f" * 64
        ref = self.fixture.put("weights/candidate.json", changed)
        binding = self.binding(manifest_ref=ref)
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)),
                          "invalid_or_unavailable_arguments")
        self.assertEqual(self.fixture.authenticated, [])

    def test_new_manifest_version_does_not_replace_the_host_pinned_old_version(self):
        changed = deepcopy(self.fixture.manifest)
        changed["runtime"]["implementation_sha256"] = "f" * 64
        self.fixture.put("weights/candidate.json", changed)
        self.assertIs(self.call(self.dispatcher())["ok"], True)
        observed = self.fixture.authenticated[0]["observation"]
        self.assertEqual(observed["manifest_ref"], self.fixture.manifest_ref)

    def test_corrupted_manifest_bytes_are_rejected(self):
        self.fixture.corrupt(self.fixture.manifest_ref)
        # Registry corruption raises RuntimeError; preserve the existing bounded
        # internal-error mapping rather than misclassifying it as caller input.
        self.assert_error(self.call(self.dispatcher()), "internal_error")
        self.assertEqual(self.fixture.authenticated, [])

    def test_corrupted_receipt_bytes_are_rejected(self):
        self.fixture.corrupt(self.result["coder_a_weight_receipt_ref"])
        self.assert_error(self.call(self.dispatcher()), "internal_error")
        self.assertEqual(self.fixture.authenticated, [])

    def test_receipt_corruption_during_authentication_cannot_publish_completed_status(self):
        calls = []
        def corrupt(receipt, checksum):
            calls.append(checksum)
            self.fixture.corrupt(self.result["coder_a_weight_receipt_ref"])
            return True
        binding = self.binding(authenticate=corrupt)
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)), "internal_error")
        self.assertEqual(len(calls), 1)

    def test_receipt_version_append_during_authentication_cannot_publish_completed_status(self):
        calls = []
        def append(receipt, checksum):
            calls.append(checksum)
            self.fixture.put("dual-coder/bound/stages/coder_a/weight-receipt.json",
                             {**receipt, "regression_fixture_version": "changed"})
            return True
        binding = self.binding(authenticate=append)
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)),
                          "invalid_or_unavailable_arguments")
        self.assertEqual(len(calls), 1)

    def test_new_receipt_version_cannot_replace_immutable_workflow_evidence(self):
        receipt, _ = self.fixture.read("dual-coder/bound/stages/coder_a/weight-receipt.json")
        receipt["observation"]["runtime_instance_id"] = "changed-instance"
        self.fixture.put("dual-coder/bound/stages/coder_a/weight-receipt.json", receipt)
        self.assert_error(self.call(self.dispatcher()), "invalid_or_unavailable_arguments")
        self.assertEqual(self.fixture.authenticated, [])

    def test_manifest_mutation_during_authentication_is_rejected(self):
        def mutate(receipt, checksum):
            self.fixture.corrupt(self.fixture.manifest_ref)
            return True
        binding = self.binding(authenticate=mutate)
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)), "internal_error")

    def test_disallowed_context_is_rejected_before_resolver(self):
        self.assert_error(self.call(self.dispatcher(namespaces=("merlin",))),
                          "invalid_or_unavailable_arguments")
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.fixture.authenticated, [])

    def test_unauthorized_uid_is_rejected_before_resolver(self):
        reply = self.call(self.dispatcher(), uid=os.geteuid() + 1)
        self.assertEqual(reply["error"], {"code": "unauthorized_peer"})
        self.assertIsNone(reply["request_id"])
        self.assertEqual(self.resolved, [])

    def test_ungranted_tool_is_rejected_before_resolver(self):
        grants = {os.geteuid(): {"principal": "synthetic-reader", "tools": ["health"]}}
        self.assert_error(self.call(self.dispatcher(grants=grants)), "tool_not_allowed")
        self.assertEqual(self.resolved, [])

    def test_invalid_session_is_rejected_before_resolver(self):
        for value in ("", "../bound", "x" * 101, 7, None):
            with self.subTest(value=value):
                self.assert_error(self.call(self.dispatcher(), session=value),
                                  "invalid_or_unavailable_arguments")
        self.assertEqual(self.resolved, [])

    def test_request_cannot_select_manifest_provider_or_configuration(self):
        for field in ("manifest_ref", "provider", "config", "rsi_weight_binding_resolver"):
            with self.subTest(field=field):
                self.assert_error(self.call(self.dispatcher(), arguments={"session_id": "bound", field: "value"}),
                                  "invalid_or_unavailable_arguments")
        self.assertEqual(self.resolved, [])

    def test_not_started_session_never_resolves_a_binding(self):
        reply = self.call(self.dispatcher(), session="not-started")
        self.assertEqual(reply["result"], {"session_id": "not-started", "status": "not_started",
                                          "next_stage": "coder_a"})
        self.assertEqual(self.resolved, [])

    def test_legacy_v1_status_does_not_invoke_configured_resolver(self):
        workflow = DualCoderWorkflow(self.fixture.registry, project_id="test")
        def coder_a(request):
            self.fixture.calls["coder_a"] += 1
            return self.fixture.payload()
        result = self.fixture.run_workflow("legacy", workflow=workflow, coder_a=coder_a)
        self.expected_provider_calls = dict(self.fixture.calls)
        self.assertEqual(result["schema"], "dot-dual-coder-report/1")
        def forbidden(session):
            self.fail("legacy status must not consult a weight binding resolver")
        reply = self.call(self.dispatcher(resolver=forbidden), session="legacy")
        self.assertIs(reply["ok"], True)
        self.assertEqual(reply["result"]["schema"], "dot-dual-coder-status/1")
        self.assertEqual(reply["result"]["status"], "completed_research_only")

    def test_resolver_and_authenticator_exception_details_are_not_returned(self):
        private = "private-host-detail-" * 1000
        def fail(*args):
            raise RuntimeError(private)
        self.assert_error(self.call(self.dispatcher(resolver=fail)), "internal_error")
        binding = self.binding(authenticate=fail)
        self.assert_error(self.call(self.dispatcher(resolver=lambda session: binding)), "internal_error")

    def test_status_keeps_registry_mutations_and_sql_writes_denied(self):
        before = _file_identity(self.reader.root)
        self.assertIs(self.call(self.dispatcher())["ok"], True)
        with self.assertRaises(PermissionError):
            self.reader.put_artifact("test", "status/unwanted.json", b"{}", "application/json")
        connection = self.reader._connect()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("CREATE TABLE unwanted_status_write(value TEXT)")
        finally:
            connection.close()
        self.assertEqual(_file_identity(self.reader.root), before)

    def test_cli_keeps_binding_resolver_unconfigured_and_config_cannot_inject_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            config_path = Path(temporary) / "config.json"
            config = {"schema": "merlin-private-host/1", "project_id": "test", "namespaces": ["rsi"],
                      "grants": [{"uid": os.geteuid(), "principal": "synthetic-reader", "tools": ["rsi_status"]}]}
            config_path.write_bytes(canonical(config))
            config_path.chmod(0o600)
            with patch("sys.argv", ["private_runtime", "serve", "--root", str(self.reader.root),
                                    "--socket", str(Path(temporary) / "host.sock"), "--config", str(config_path)]), \
                 patch("dot_ai_os.private_runtime.PrivateUnixServer") as server:
                self.assertEqual(main(), 0)
            dispatcher = server.call_args.args[1]
            self.assertIsNone(dispatcher.rsi_weight_binding_resolver)
            self.assertIsInstance(dispatcher.bridge.registry, PrivateReadOnlyRegistry)
            self.assert_error(self.call(dispatcher), "weight_binding_not_configured")
            config["rsi_weight_binding_resolver"] = "untrusted.module"
            config_path.write_bytes(canonical(config))
            with self.assertRaises(PrivateHostConfigurationError):
                load_configuration(config_path)


if __name__ == "__main__":
    unittest.main()
