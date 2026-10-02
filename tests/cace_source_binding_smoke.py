#!/usr/bin/env python3
"""Exercise the generated CACE publisher against a local moved source branch."""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_cace_return.py"
external = (ROOT / ".github/workflows/external-free-runner-bridge.yml").read_text()
publisher = external.split("- name: Return passed evidence to Expert Robot\n", 1)[1]
publisher = publisher.split("- name: Remove reverse deploy key\n", 1)[0]
publisher = textwrap.dedent(publisher.split("run: |\n", 1)[1]).strip() + "\n"

# Execute the workflow's code, excluding only its external publishing operation.
push_start = publisher.rfind("\nGIT_SSH_COMMAND=")
assert push_start > 0
assert 'git push --force-with-lease origin "HEAD:$return_branch"' in publisher[push_start:]
evidence_script = publisher[:push_start] + "\n"
assert "git push" not in evidence_script
checkout_script = evidence_script.split('\nmkdir -p "$evidence_dir"', 1)[0] + "\n"
assert "git clone --no-checkout" in checkout_script
assert 'git fetch --no-tags origin "$SOURCE_SHA"' in checkout_script
assert 'test "$(git rev-parse HEAD)" = "$SOURCE_SHA"' in checkout_script
assert 'test "$(git rev-list --parents -n 1 HEAD)" = "$(git rev-parse HEAD) $SOURCE_SHA"' in evidence_script


def run(*args, cwd=None, env=None, check=True, input=None):
    result = subprocess.run(
        args, cwd=cwd, env=env, input=input, text=True, capture_output=True
    )
    if check:
        assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    # Local file transport only: accidental network use must fail this test.
    env = dict(os.environ)
    env.update({
        "GIT_ALLOW_PROTOCOL": "file",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "cace-source-test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "cace-source-test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })

    def git(repo, *args, check=True, input=None):
        return run("git", "-C", str(repo), *args, env=env, check=check, input=input)

    seed = root / "seed"
    run("git", "init", "--initial-branch=main", str(seed), env=env)
    (seed / "source.txt").write_text("qualified source\n")
    git(seed, "add", "source.txt")
    git(seed, "commit", "-m", "qualified source")
    source_sha = git(seed, "rev-parse", "HEAD").stdout.strip()
    blob_sha = git(seed, "rev-parse", "HEAD:source.txt").stdout.strip()
    tree_sha = git(seed, "rev-parse", "HEAD^{tree}").stdout.strip()

    # Qualification has finished; the named branch advances before publication.
    (seed / "source.txt").write_text("branch moved after qualification\n")
    git(seed, "add", "source.txt")
    git(seed, "commit", "-m", "source branch advanced")
    moved_sha = git(seed, "rev-parse", "HEAD").stdout.strip()
    assert moved_sha != source_sha
    bare = root / "source.git"
    run("git", "clone", "--bare", str(seed), str(bare), env=env)
    refs_before = git(bare, "show-ref").stdout
    assert git(bare, "rev-parse", "refs/heads/main").stdout.strip() == moved_sha
    missing_sha = "f" * 40
    assert git(bare, "cat-file", "-e", missing_sha, check=False).returncode != 0

    def publish(label, sha, script):
        case = root / label
        workspace = case / "workspace"
        runner = case / "runner"
        (workspace / "bridge").mkdir(parents=True)
        result_dir = runner / "expert-robot-bridge-result"
        result_dir.mkdir(parents=True)
        request_id = "source-binding-test"
        (workspace / "bridge/request.json").write_text(json.dumps({
            "request_id": request_id,
            "source_branch": "main",
            "return_repository": "Mannyspiro/expert-robot",
            "expert_robot_commit": sha,
        }))
        (result_dir / "result.json").write_text(json.dumps({
            "request_id": request_id, "status": "pass", "expert_robot_commit": sha,
        }))
        case_env = dict(env, RUNNER_TEMP=str(runner), GITHUB_WORKSPACE=str(workspace),
                        KEY_FILE=str(case / "unused-local-transport-key"),
                        REQUEST_ID=request_id, SOURCE_SHA=sha,
                        EXPERT_ROBOT_REPO_SSH=str(bare))
        result = run("bash", "-c", script, cwd=workspace, env=case_env, check=False)
        return result, runner / "expert-robot-return", request_id

    result, checkout, request_id = publish("checkout", source_sha, checkout_script)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert git(checkout, "rev-parse", "HEAD").stdout.strip() == source_sha
    assert git(checkout, "rev-parse", "origin/main").stdout.strip() == moved_sha
    assert (checkout / "source.txt").read_text() == "qualified source\n"
    assert git(checkout, "branch", "--show-current").stdout.strip() == f"cace-return/{request_id}"

    for label, sha in (
        ("missing", missing_sha),
        ("blob", blob_sha),
        ("tree", tree_sha),
        ("malformed", "not-a-commit"),
        ("short", source_sha[:-1]),
        ("uppercase", "A" + source_sha[1:]),
    ):
        result, rejected, request_id = publish(label, sha, checkout_script)
        assert result.returncode != 0, (label, result.stdout, result.stderr)
        assert not (rejected / ".cace-return.json").exists(), label
        if (rejected / ".git").exists():
            assert git(rejected, "show-ref", "--verify", f"refs/heads/cace-return/{request_id}",
                       check=False).returncode != 0, label
            if label in {"blob", "tree"}:
                # Fetch succeeded; the object's type caused rejection before checkout.
                assert git(rejected, "rev-parse", "FETCH_HEAD").stdout.strip() == sha
                assert git(rejected, "cat-file", "-t", sha).stdout.strip() == label
        else:
            assert label in {"malformed", "short", "uppercase"}, label

    # The real generated envelope and evidence commit pass validation.
    result, returned, request_id = publish("evidence", source_sha, evidence_script)
    assert result.returncode == 0, (result.stdout, result.stderr)
    evidence_sha = git(returned, "rev-parse", "HEAD").stdout.strip()
    assert git(returned, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split() == [evidence_sha, source_sha]
    assert (returned / "source.txt").read_text() == "qualified source\n"
    assert (returned / f".cace/evidence/{request_id}/request.json").is_file()
    assert (returned / f".cace/evidence/{request_id}/result.json").is_file()
    envelope = returned / ".cace-return.json"
    payload = json.loads(envelope.read_text())

    def validate(check=True):
        return run(sys.executable, str(VALIDATOR), str(envelope), f"cace-return/{request_id}",
                   env=env, check=check)

    normalized = json.loads(validate().stdout)
    assert normalized["source_sha"] == source_sha
    assert normalized["base_branch"] == "main"

    for sha, message in (
        (missing_sha, "return source commit is unavailable"),
        (blob_sha, "return source is not a commit"),
        (tree_sha, "return source is not a commit"),
        ("not-a-commit", "invalid source commit"),
    ):
        envelope.write_text(json.dumps(dict(payload, expert_robot_commit=sha)))
        invalid = validate(check=False)
        assert invalid.returncode != 0
        assert message in invalid.stderr, (sha, invalid.stdout, invalid.stderr)
    envelope.write_text(json.dumps(payload, indent=2) + "\n")

    # Keeping the qualified SHA as an ancestor is insufficient if code intervened.
    git(returned, "checkout", "--detach", source_sha)
    (returned / "unrelated.txt").write_text("intervening code\n")
    git(returned, "add", "unrelated.txt")
    git(returned, "commit", "-m", "intervening source change")
    intermediate_sha = git(returned, "rev-parse", "HEAD").stdout.strip()
    git(returned, "cherry-pick", evidence_sha)
    assert git(returned, "rev-parse", "HEAD^").stdout.strip() == intermediate_sha
    invalid = validate(check=False)
    assert invalid.returncode != 0
    assert "exactly one parent equal to source SHA" in invalid.stderr

    # Even an evidence-only merge with the correct first parent must be rejected.
    evidence_tree = git(returned, "rev-parse", f"{evidence_sha}^{{tree}}").stdout.strip()
    merge_sha = git(returned, "commit-tree", evidence_tree, "-p", source_sha,
                    "-p", intermediate_sha, input="evidence merge\n").stdout.strip()
    git(returned, "checkout", "--detach", merge_sha)
    assert git(returned, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split() == [
        merge_sha, source_sha, intermediate_sha,
    ]
    invalid = validate(check=False)
    assert invalid.returncode != 0
    assert "exactly one parent equal to source SHA" in invalid.stderr
    assert git(bare, "show-ref").stdout == refs_before

print("CACE source binding smoke: PASS")
