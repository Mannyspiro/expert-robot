"""Prevent regression of Merlin's exact-revision GitLab CI source contract.

This stdlib-only check validates required pinned-source boundaries, not arbitrary
YAML syntax or GitLab's own pipeline compiler. GitLab CI remains authoritative
for execution and source state is reconciled separately.
"""
from pathlib import Path
import re
import unittest


TEMPLATE = Path(__file__).resolve().parents[1] / "ci" / "gitlab-merlin-exact-revision.yml"


def verify_template(content: str) -> str:
    if not isinstance(content, str) or len(content) > 128 * 1024:
        raise ValueError("bounded UTF-8 GitLab template required")
    required = (
        "spec:\n  inputs:\n    github_sha:\n",
        "type: string",
        "regex: '^[0-9a-f]{40}$'",
        'MERLIN_GITHUB_SHA: "$[[ inputs.github_sha ]]"',
        'if: \'$CI_PIPELINE_SOURCE == "api"\'',
        "GIT_STRATEGY: none",
        "libsqlite3-dev",
        'git clone --no-checkout https://github.com/Mannyspiro/expert-robot.git merlin',
        'git fetch origin "$MERLIN_GITHUB_SHA"',
        'git checkout --detach "$MERLIN_GITHUB_SHA"',
        'test "$(git rev-parse HEAD)" = "$MERLIN_GITHUB_SHA"',
        "merlin_hybrid_preflight.py --root . --expected-sha",
        "run_merlin_offline_ci.sh",
        "when: always",
        "expire_in: 14 days",
        "- merlin-evidence/",
        "- merlin-preflight.json",
    )
    for marker in required:
        if marker not in content:
            raise ValueError("GitLab exact-revision gate missing: " + marker)
    if content.count('if: \'$CI_PIPELINE_SOURCE == "api"\'') != 2:
        raise ValueError("both workflow and job require API-only rule")
    if any(block in content for block in (
        "when: manual", 'CI_PIPELINE_SOURCE == "push"',
        'CI_PIPELINE_SOURCE == "web"', "git checkout main",
        'MERLIN_GITHUB_SHA: "main"',
    )):
        raise ValueError("implicit, human/manual or moving branch execution forbidden")
    found = re.findall(r'^\s*default: "([0-9a-f]{40})"\s*$', content, re.MULTILINE)
    if len(found) != 1:
        raise ValueError("one frozen reviewed SHA default required")
    if "    - when: never" not in content:
        raise ValueError("non-API pipelines must be rejected")
    return found[0]


class GitLabExactSourceContractTests(unittest.TestCase):
    def test_repository_template_pin_is_exact_and_api_input_only(self):
        pinned = verify_template(TEMPLATE.read_text(encoding="utf-8"))
        self.assertRegex(pinned, r"^[a-f0-9]{40}$")

    def test_no_implicit_moving_branch_or_web_workflow(self):
        base = TEMPLATE.read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            verify_template(base.replace("- when: never", "- when: never\n  - when: manual"))
        with self.assertRaises(ValueError):
            verify_template(base.replace("git checkout --detach", "git checkout main # --detach"))

    def test_missing_source_checkout_hash_or_sqlite_dependency_fails(self):
        base = TEMPLATE.read_text(encoding="utf-8")
        for marker in ('test "$(git rev-parse HEAD)" = "$MERLIN_GITHUB_SHA"',
                       "libsqlite3-dev", 'git fetch origin "$MERLIN_GITHUB_SHA"'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                verify_template(base.replace(marker, "omitted-by-regression"))

    def test_removed_workflow_rule_or_input_binding_fails(self):
        base = TEMPLATE.read_text(encoding="utf-8")
        for marker in ('if: \'$CI_PIPELINE_SOURCE == "api"\'',
                       'MERLIN_GITHUB_SHA: "$[[ inputs.github_sha ]]"'):
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                verify_template(base.replace(marker, "misconfigured"))

    def test_unreviewed_default_ref_does_not_validate(self):
        base = TEMPLATE.read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_template(re.sub(r'default: "[a-f0-9]{40}"', 'default: "main"', base))


if __name__ == "__main__":
    unittest.main()
