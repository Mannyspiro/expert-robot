"""Fail-closed source-identity contracts for Merlin optional GitHub Actions.

A pull_request Actions run defaults to testing a synthetic merge revision.
Source artifacts must instead be built from the *actual* event head commit,
which is the immutable revision independently checked by GitLab.
These are static guard tests; an Actions runner must still prove execution.
"""
from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/merlin-airllm-openbot.yml",
    ".github/workflows/merlin-opensandbox-zai.yml",
    ".github/workflows/merlin-optional-source-audit.yml",
)
HEAD_EXPR = "${{ github.event.pull_request.head.sha || github.sha }}"
CHECKOUT_PIN = "          ref: " + HEAD_EXPR
EXPECTED_ENV = "          MERLIN_EXACT_SOURCE_SHA: " + HEAD_EXPR
HEAD_CHECK = '          test "$(git rev-parse HEAD)" = "$MERLIN_EXACT_SOURCE_SHA"'
CLEAN_CHECK = '          test -z "$(git status --porcelain --untracked-files=no)"'


def workflow_has_exact_source_guard(body: str) -> bool:
    if not isinstance(body, str):
        return False
    if ("      - uses: actions/checkout@v4" not in body
            or body.count(CHECKOUT_PIN) != 1 or body.count(EXPECTED_ENV) != 1
            or body.count(HEAD_CHECK) != 1 or body.count(CLEAN_CHECK) != 1
            or "          persist-credentials: false" not in body
            or '          [[ "$MERLIN_EXACT_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]' not in body):
        return False
    return (body.index("      - uses: actions/checkout@v4")
            < body.index(CHECKOUT_PIN)
            < body.index("      - name: Verify exact source checkout")
            < body.index(EXPECTED_ENV)
            < body.index(HEAD_CHECK)
            < body.index(CLEAN_CHECK))


class OptionalActionsProvenanceTests(unittest.TestCase):
    def test_each_workflow_binds_source_to_exact_event_head(self):
        for path in WORKFLOWS:
            with self.subTest(path=path):
                body = (ROOT / path).read_text(encoding="utf-8")
                self.assertTrue(workflow_has_exact_source_guard(body), path)

    def test_missing_checkout_pin_fails_closed_for_every_workflow(self):
        for path in WORKFLOWS:
            with self.subTest(path=path):
                body = (ROOT / path).read_text(encoding="utf-8")
                self.assertFalse(workflow_has_exact_source_guard(body.replace(CHECKOUT_PIN, "          ref: main")))

    def test_synthetic_merge_sha_or_missing_guard_fails_closed(self):
        for path in WORKFLOWS:
            body = (ROOT / path).read_text(encoding="utf-8")
            for corrupt in (
                    body.replace(CHECKOUT_PIN, "          ref: ${{ github.sha }}"),
                    body.replace(EXPECTED_ENV, "          MERLIN_EXACT_SOURCE_SHA: ${{ github.sha }}"),
                    body.replace(HEAD_CHECK, "          echo 'source check skipped'"),
                    body.replace(CLEAN_CHECK, "          echo 'clean check skipped'"),
            ):
                with self.subTest(path=path, mutation=corrupt != body):
                    self.assertFalse(workflow_has_exact_source_guard(corrupt))

    def test_dispatch_and_pull_request_preserve_fallback(self):
        for path in WORKFLOWS:
            with self.subTest(path=path):
                body = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("  pull_request:", body)
                self.assertIn("  workflow_dispatch:", body)
                self.assertEqual(body.count(HEAD_EXPR), 2)

    def test_uncleared_upstream_source_export_stays_metadata_only(self):
        body = (ROOT / WORKFLOWS[1]).read_text(encoding="utf-8")
        self.assertIn('"source_review_status":"blocked"', body)
        self.assertIn('"upstream_source_bytes_in_artifact":False', body)
        self.assertIn("          path: source-review/", body)
        self.assertNotIn("          path: bundle/", body)
        self.assertIn("          test ! -e bundle/merlin-opensandbox-zai-graft-source.zip", body)
        # The old source workflow ran git archive directly from both optional
        # upstream trees; banning the specific old commands catches that
        # regression even if the bundle ZIP is renamed.
        for old_raw_export in (
            "git -C third_party/opensandbox archive HEAD",
            "git -C third_party/graft archive HEAD",
            "tar -xf - -C bundle/",
            "zip -qr merlin-opensandbox-zai-graft-source.zip",
        ):
            with self.subTest(old_raw_export=old_raw_export):
                self.assertNotIn(old_raw_export, body)


    def test_upstream_scan_retains_all_four_reports_and_nonzero_gate(self):
        body = (ROOT / WORKFLOWS[2]).read_text(encoding="utf-8")
        for name in ("airllm", "openbot", "opensandbox", "graft"):
            self.assertIn("--output optional-source-audit/" + name + ".json", body)
        self.assertIn('          exit "$audit_failed"', body)
        self.assertIn("        if: always()", body)


if __name__ == "__main__":
    unittest.main()
