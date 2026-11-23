#!/usr/bin/env python3
"""Rendered Chromium evidence for actual Merlin Studio approval and cancellation.

Uses a real local Studio server, actual Playwright page interactions and
test-owned host Python scripts. Sandbox mode is a disclosure/denial-only test:
there is no sandbox controller and no remote code is executed in that phase.
The separate native CI suite proves the Docker execution boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright, expect

STUDIO = Path(__file__).resolve().parents[2] / "portable" / "merlin_studio"
ADDRESS = re.compile(r"^Merlin Studio: http://127\.0\.0\.1:(\d+)/studio/$")
IMAGE = "registry.example/merlin-browser-fixture@sha256:" + "c" * 64


def require(value, detail):
    if not value:
        raise AssertionError(detail)


def request_run(port, run_id):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        conn.request("GET", "/api/runs/" + run_id,
                     headers={"Host": "127.0.0.1:" + str(port)})
        response = conn.getresponse()
        body = json.loads(response.read(300000))
        require(response.status == 200, "Run HTTP retrieval failed")
        return body["run"]
    finally:
        conn.close()


def wait_run(port, run_id, predicate, *, timeout=18):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        run = request_run(port, run_id)
        if predicate(run):
            return run
        time.sleep(0.05)
    raise AssertionError("Real Studio run did not reach expected state: " + run_id)


def start_studio(data_dir, *, backend):
    env = os.environ.copy()
    env.pop("MERLIN_MODEL_URL", None)
    env.pop("MERLIN_MODEL_ID", None)
    env.pop("OPEN_SANDBOX_API_KEY", None)
    env["MERLIN_PYTHON_BACKEND"] = backend
    env["PYTHONUNBUFFERED"] = "1"
    if backend == "opensandbox":
        env["MERLIN_SANDBOX_IMAGE"] = IMAGE
        env["MERLIN_SANDBOX_PORT"] = "8080"
    else:
        env.pop("MERLIN_SANDBOX_IMAGE", None)
        env.pop("MERLIN_SANDBOX_PORT", None)
    data_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [sys.executable, "-B", str(STUDIO / "server.py"), "--port", "0",
         "--data-dir", str(data_dir)],
        cwd=str(STUDIO), env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        until = time.monotonic() + 16
        while time.monotonic() < until:
            require(proc.poll() is None, "Test-owned Studio terminated before startup")
            ready, _, _ = select.select([proc.stdout], [], [], 0.2)
            if ready:
                line = proc.stdout.readline().decode("utf-8", "replace").strip()
                match = ADDRESS.fullmatch(line)
                if match:
                    return proc, int(match.group(1))
        raise AssertionError("Studio never printed a loopback server address")
    except BaseException:
        stop_studio(proc)
        raise


def stop_studio(proc):
    if proc is None:
        return
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.wait(timeout=8)
    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()


def open_page(browser, port, *, mobile=False):
    context = browser.new_context(
        viewport={"width": 390, "height": 844} if mobile else {"width": 1360, "height": 850},
        device_scale_factor=1, is_mobile=mobile, has_touch=mobile)
    page = context.new_page()
    page.set_default_timeout(16000)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:" + str(port) + "/studio/", wait_until="domcontentloaded")
    expect(page.locator("#server-label")).to_contain_text("Studio", timeout=15000)
    return context, page, errors


def submit(page, message):
    box = page.locator("#message-input")
    box.fill(message)
    send = page.locator("#send-button")
    expect(send).to_be_enabled()
    send.click()


def pending(page):
    card = page.locator("section.approval-card")
    expect(card).to_be_visible(timeout=15000)
    run_id = page.evaluate("() => localStorage.getItem('merlin.run')")
    require(isinstance(run_id, str) and len(run_id) == 32,
            "Rendered approval lacked active canonical run identity")
    return card, run_id


def event_count(run, event_type):
    return sum(x.get("type") == event_type for x in run.get("events", []))


def host_approval(browser, data_dir, evidence):
    workspace = data_dir / "workspace"
    workspace.mkdir(parents=True)
    source = b"print('MERLIN_RENDERED_HOST_OK')\n"
    (workspace / "answer.py").write_bytes(source)
    (workspace / "hang.py").write_text(
        "from pathlib import Path\nfrom time import sleep\n"
        "Path('browser-script-started.signal').write_text('started')\nsleep(60)\n",
        encoding="utf-8")
    proc = None
    context = None
    page = None
    try:
        proc, port = start_studio(data_dir, backend="host")
        context, page, errors = open_page(browser, port)
        page.locator("#settings-top").click()
        expect(page.locator("#python-description")).to_contain_text(
            "Host Python runs with your local user permissions")
        require("not an OS sandbox" in page.locator("#python-description").inner_text(),
                "Host risk warning was suppressed")
        page.screenshot(path=str(evidence / "host-settings.png"), full_page=True)
        page.locator('#settings-backdrop [data-close="settings"]').first.click()

        submit(page, "/python answer.py")
        card, denied_id = pending(page)
        expect(card).to_contain_text("your local user")
        require(hashlib.sha256(source).hexdigest() in card.inner_text(),
                "Host script digest omitted from approval")
        page.screenshot(path=str(evidence / "host-pending-denial.png"), full_page=True)
        card.get_by_role("button", name="Decline").click()
        denied = wait_run(port, denied_id, lambda r: r["status"] == "completed")
        require(event_count(denied, "tool_denied") == 1
                and event_count(denied, "tool_started") == 0
                and event_count(denied, "tool_result") == 0,
                "Denied host Python script was executed or misreported")
        page.locator("#activity-toggle").click()
        expect(page.locator("#activity-feed")).to_contain_text("Action declined")
        page.screenshot(path=str(evidence / "host-denial-activity.png"), full_page=True)

        submit(page, "/python answer.py")
        card, approved_id = pending(page)
        card.get_by_role("button", name="Approve once").click()
        approved = wait_run(port, approved_id, lambda r: r["status"] == "completed")
        results = [x for x in approved["events"] if x["type"] == "tool_result"]
        require(len(results) == 1
                and "MERLIN_RENDERED_HOST_OK" in results[0]["result"]["stdout"]
                and results[0]["result"]["script_sha256"] == hashlib.sha256(source).hexdigest()
                and results[0]["result"]["os_sandbox"] is False
                and results[0].get("artifact_ref", {}).get("sha256"),
                "Approved host tool result or canonical artifact differed")
        expect(page.locator("#messages")).to_contain_text("MERLIN_RENDERED_HOST_OK",
                                                         timeout=15000)
        expect(page.locator("#activity-feed")).to_contain_text("Tool completed")
        page.screenshot(path=str(evidence / "host-approved-activity.png"), full_page=True)

        submit(page, "/python hang.py")
        card, stop_id = pending(page)
        card.get_by_role("button", name="Approve once").click()
        wait_run(port, stop_id, lambda r: event_count(r, "tool_started") >= 1)
        start_signal = workspace / "browser-script-started.signal"
        until = time.monotonic() + 10
        while not start_signal.exists() and time.monotonic() < until:
            time.sleep(.06)
        require(start_signal.exists(), "Live host subprocess never began")
        stop = page.locator('#send-button[aria-label="Stop current run"]')
        expect(stop).to_be_enabled(timeout=10000)
        stop.click()
        cancelled = wait_run(port, stop_id, lambda r: r["status"] in ("cancelled", "failed"))
        require(cancelled["status"] == "cancelled"
                and event_count(cancelled, "cancel_requested") == 1
                and event_count(cancelled, "tool_result") == 0,
                "Host cancellation was prematurely reported complete")
        expect(page.locator("#messages")).to_contain_text("This run was stopped",
                                                         timeout=15000)
        expect(page.locator("#activity-feed")).to_contain_text(
            "Stop requested (verifying cleanup)")
        page.screenshot(path=str(evidence / "host-cancelled-activity.png"), full_page=True)
        require(not errors, "Browser JavaScript failed: " + repr(errors))
        return {
            "real_browser": True, "mode": "host", "approval_denied_executions": 0,
            "approved_executions": 1, "host_risk_disclosed": True,
            "approved_source_sha256": hashlib.sha256(source).hexdigest(),
            "canonical_result_artifact": results[0]["artifact_ref"]["sha256"],
            "stop_requested_event": True, "host_process_observed_before_cancel": True,
            "false_completed_tool_results_after_cancel": 0,
            "outcomes": [denied["status"], approved["status"], cancelled["status"]],
        }
    finally:
        if page is not None:
            try:
                page.screenshot(path=str(evidence / "host-last.png"), full_page=True)
            except Exception:
                pass
        if context is not None:
            context.close()
        stop_studio(proc)


def sandbox_disclosure(browser, data_dir, evidence):
    workspace = data_dir / "workspace"
    workspace.mkdir(parents=True)
    source = b"print('UNREACHABLE_NO_CONTROLLER')\n"
    (workspace / "answer.py").write_bytes(source)
    proc, context, page = None, None, None
    try:
        proc, port = start_studio(data_dir, backend="opensandbox")
        context, page, errors = open_page(browser, port, mobile=True)
        page.locator("#settings-top").click()
        expect(page.locator("#python-description")).to_contain_text(
            "Isolated OpenSandbox mode is selected")
        expect(page.locator("#settings-note")).to_contain_text(
            "controller and container runtime")
        page.screenshot(path=str(evidence / "sandbox-mobile-settings.png"), full_page=True)
        page.locator('#settings-backdrop [data-close="settings"]').first.click()
        submit(page, "/python answer.py")
        card, run_id = pending(page)
        expect(card).to_contain_text("operator-configured OpenSandbox container")
        require(IMAGE in card.inner_text(), "Approved image digest missing from browser")
        require("with your local user" not in card.inner_text(),
                "Incorrect host permission warning was displayed in sandbox mode")
        page.screenshot(path=str(evidence / "sandbox-mobile-pending.png"), full_page=True)
        card.get_by_role("button", name="Decline").click()
        denied = wait_run(port, run_id, lambda r: r["status"] == "completed")
        require(event_count(denied, "tool_denied") == 1
                and event_count(denied, "tool_started") == 0
                and event_count(denied, "tool_result") == 0,
                "Sandbox denial started a remote or host execution")
        require(not errors, "Mobile browser JavaScript failed: " + repr(errors))
        page.screenshot(path=str(evidence / "sandbox-mobile-denied.png"), full_page=True)
        return {
            "real_browser": True, "mode": "opensandbox",
            "image": IMAGE, "sandbox_risk_disclosed": True, "mobile_viewport": True,
            "denied_executions": 0, "remote_controller_installed": False,
            "remote_sandbox_created": False, "outcome": denied["status"],
        }
    finally:
        if page is not None:
            try:
                page.screenshot(path=str(evidence / "sandbox-last.png"), full_page=True)
            except Exception:
                pass
        if context is not None:
            context.close()
        stop_studio(proc)


def main():
    parser = argparse.ArgumentParser(description="Verify rendered Studio approval and activity")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.output_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="merlin-rendered-browser-") as directory:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                host = host_approval(browser, Path(directory) / "host", evidence)
                sandbox = sandbox_disclosure(browser, Path(directory) / "sandbox", evidence)
                receipt = {
                    "schema": "merlin-rendered-studio-approval/1",
                    "browser": "Chromium via Playwright",
                    "real_browser_clicks": True,
                    "test_owned_host_scripts_only": True,
                    "real_docker_executed": False,
                    "host": host,
                    "sandbox": sandbox,
                }
                (evidence / "rendered-studio-receipt.json").write_text(
                    json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(receipt, sort_keys=True))
            finally:
                browser.close()


if __name__ == "__main__":
    main()
