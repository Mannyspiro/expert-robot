#!/usr/bin/env node
/**
 * Render and exercise real Studio browser approval UI on an ephemeral runner.
 *
 * Core events are real local Studio HTTP + approved host test scripts.
 * The visually held "cancelling" state and sandbox/capability copy checks are
 * explicitly intercepted UI fixtures; they are NOT real Docker observations.
 * Native Docker approval/cancellation is independently tested in parent CI.
 */
import assert from "node:assert/strict";
import {spawn} from "node:child_process";
import {mkdtemp, mkdir, writeFile, rm} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import readline from "node:readline";
import {chromium} from "playwright";

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const studio = path.join(project, "portable", "merlin_studio");
const evidence = process.argv[2] || path.join(os.tmpdir(), "merlin-browser-evidence");
const root = await mkdtemp(path.join(os.tmpdir(), "merlin-real-browser-"));
const data = path.join(root, "data");
const workspace = path.join(data, "workspace");
await mkdir(workspace, {recursive:true});
await mkdir(evidence, {recursive:true});
await writeFile(path.join(workspace, "deny.py"),
  "from pathlib import Path\nPath('DENIED_MARKER').write_text('unsafe')\n");
await writeFile(path.join(workspace, "approved.py"), "print('MERLIN_BROWSER_APPROVED_OK')\n");
await writeFile(path.join(workspace, "long.py"),
  "import time\nprint('MERLIN_BROWSER_LONG_RUNNING', flush=True)\ntime.sleep(25)\n");
let server = null;
let browser = null;
const errors = [];
const observations = {
  schema:"merlin-studio-rendered-ui-acceptance/1",
  real_chromium:true,
  real_studio_http:true,
  real_local_host_python:true,
  controlled_synthetic_scripts:true,
  real_docker_in_this_job:false,
  model_inference_calls:0,
  remote_accounts_or_secrets:false,
  ui_cancelling_hold_is_intercepted_fixture:true,
  sandbox_capability_copy_is_intercepted_fixture:true,
  tests:{}
};

async function launch() {
  const env = {...process.env, MERLIN_PYTHON_BACKEND:"host", PYTHONDONTWRITEBYTECODE:"1"};
  delete env.MERLIN_SANDBOX_IMAGE;
  delete env.OPEN_SANDBOX_API_KEY;
  const proc = spawn(process.env.PYTHON || "python3",
    ["-B", "server.py", "--port", "0", "--data-dir", data],
    {cwd:studio, env, stdio:["ignore", "pipe", "pipe"], detached:true});
  server = proc;
  let stderr = "";
  proc.stderr.on("data", x => {stderr = (stderr+x.toString()).slice(-4000);});
  let timer = null;
  return await new Promise((resolve, reject) => {
    let complete = false;
    const finish = (error, value) => {
      if(complete) return;
      complete = true;
      clearTimeout(timer);
      error ? reject(error) : resolve(value);
    };
    timer = setTimeout(()=>finish(new Error("Studio startup timed out: "+stderr)), 18000);
    proc.once("exit", (code)=>finish(new Error("Studio exited "+code+": "+stderr)));
    readline.createInterface({input:proc.stdout}).on("line", line=>{
      const match = /^Merlin Studio: (http:\/\/127\.0\.0\.1:\d+)\/studio\/$/.exec(line.trim());
      if(match) finish(null,match[1]);
    });
  });
}

async function runStatus(base, runId) {
  const reply = await fetch(base+"/api/runs/"+encodeURIComponent(runId));
  assert.equal(reply.status,200);
  return (await reply.json()).run;
}
async function terminal(base, runId, timeout=15000) {
  const start = Date.now();
  while(Date.now()-start<timeout) {
    const run = await runStatus(base,runId);
    if(["completed","failed","cancelled","interrupted"].includes(run.status)) return run;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error("Run did not reach terminal state: "+runId);
}
async function send(page, command) {
  await page.locator("#message-input").fill(command);
  await page.locator('#send-button[aria-label="Send message"]').waitFor({state:"visible",timeout:15000});
  await page.waitForFunction(() => {
    const button = document.querySelector("#send-button");
    return button && !button.disabled && button.getAttribute("aria-label")==="Send message";
  }, null, {timeout:15000});
  const replyWait = page.waitForResponse(response =>
    response.request().method()==="POST" && new URL(response.url()).pathname==="/api/chat", {timeout:15000});
  await page.locator("#send-button").click();
  const response = await replyWait;
  assert.equal(response.status(),202,"Browser chat submission failed");
  const body = await response.json();
  assert.match(body.run_id,/^[0-9a-f]{32}$/);
  return body.run_id;
}
async function waitForText(page, selector, fragment, timeout=12000) {
  await page.waitForFunction(([sel,str]) =>
    [...document.querySelectorAll(sel)].some(node=>node.textContent.includes(str)),
    [selector,fragment], {timeout});
}
async function stop() {
  if (browser) await browser.close().catch(()=>{});
  if (server && server.exitCode===null) {
    try {process.kill(-server.pid, "SIGKILL");} catch {}
    await new Promise(resolve=>server.once("exit",()=>resolve()));
  }
  await rm(root, {recursive:true,force:true});
}

try {
  const base = await launch();
  browser = await chromium.launch({headless:true,args:["--no-sandbox"]});
  const context = await browser.newContext({viewport:{width:1390,height:900},
    reducedMotion:"reduce"});
  const page = await context.newPage();
  page.on("pageerror", e=>errors.push(e.message));
  await page.goto(base+"/studio/",{waitUntil:"domcontentloaded",timeout:20000});
  await waitForText(page,"#server-label","Studio",12000);
  assert.equal(await page.locator("#message-input").isVisible(),true);
  observations.tests.desktop_boot = true;

  // Real denial through the rendered card, not direct API approval.
  const deniedRun = await send(page,"/python deny.py");
  await page.locator(".approval-card").waitFor({state:"visible",timeout:15000});
  await waitForText(page,".approval-card","This executes code with your local user’s permissions");
  await page.screenshot({path:path.join(evidence,"01-approval-host.png"),fullPage:true});
  await page.getByRole("button",{name:"Decline"}).click();
  const denied = await terminal(base,deniedRun);
  assert.equal(denied.status,"completed");
  assert(denied.events.some(e=>e.type==="tool_denied"));
  assert(!denied.events.some(e=>e.type==="tool_result"));
  const marker = await import("node:fs/promises").then(fs => fs.access(path.join(workspace,"DENIED_MARKER"))
    .then(()=>true).catch(()=>false));
  assert.equal(marker,false,"Denied script executed unexpectedly");
  observations.tests.visual_denial_no_execution = true;

  await page.locator("#activity-toggle").click();
  await waitForText(page,"#activity-feed","Action declined");
  await page.screenshot({path:path.join(evidence,"02-denial-activity.png"),fullPage:true});
  observations.tests.activity_records_denial = true;

  // Real user approval on synthetic source; verify actual host worker receipt.
  const approvedRun = await send(page,"/python approved.py");
  await page.locator(".approval-card").waitFor({state:"visible",timeout:15000});
  await waitForText(page,".approval-card pre","script_sha256");
  await page.getByRole("button",{name:"Approve once"}).click();
  const completed = await terminal(base,approvedRun);
  assert.equal(completed.status,"completed",JSON.stringify(completed).slice(0,400));
  const results = completed.events.filter(e=>e.type==="tool_result");
  assert.equal(results.length,1);
  assert(results[0].result.stdout.includes("MERLIN_BROWSER_APPROVED_OK"));
  assert(results[0].artifact_ref && results[0].artifact_ref.sha256);
  await waitForText(page,"#activity-feed","Tool completed");
  await page.screenshot({path:path.join(evidence,"03-approved-and-evidence.png"),fullPage:true});
  observations.tests.visual_approval_with_canonical_artifact = true;

  // Actual host cancellation, with an explicit, synthetic held browser state
  // to inspect the nonterminal "Stopping" wording deterministically.
  const longRun = await send(page,"/python long.py");
  await page.locator(".approval-card").waitFor({state:"visible",timeout:15000});
  await page.getByRole("button",{name:"Approve once"}).click();
  await page.locator('#send-button[aria-label="Stop current run"]').waitFor({state:"visible",timeout:10000});
  let holdCancelledView = true;
  await page.route("**/api/runs/*",async route=>{
    if(route.request().method()==="GET" && holdCancelledView) {
      const real = await route.fetch();
      if(real.ok()) {
        const data = await real.json();
        if(data.run) {
          data.run.status = "cancelling";
          data.run.pending_approval = null;
          await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(data)});
          return;
        }
      }
    }
    await route.continue();
  });
  await page.locator('#send-button[aria-label="Stop current run"]').click();
  await waitForText(page,".run-notice","Stopping — verifying cleanup…",12000);
  assert.equal(await page.locator("#send-button").isDisabled(),true,
    "Browser allowed duplicate Stop while cleanup is pending");
  await page.screenshot({path:path.join(evidence,"04-cancelling-ui-fixture.png"),fullPage:true});
  holdCancelledView = false;
  const cancelled = await terminal(base,longRun,15000);
  assert.equal(cancelled.status,"cancelled",JSON.stringify(cancelled).slice(0,350));
  assert(!cancelled.events.some(e=>e.type==="tool_result"),"Cancelled run claimed successful tool result");
  observations.tests.real_cancel_no_success_receipt = true;
  observations.tests.simulated_provisional_cancelling_visual = true;
  await page.unroute("**/api/runs/*");

  // Full browser reload restores the saved conversation and run Activity.
  await page.reload({waitUntil:"domcontentloaded"});
  await waitForText(page,"#server-label","Studio");
  await waitForText(page,"#messages","/python approved.py");
  observations.tests.reload_preserves_messages = true;

  // Display mode selection is a visual fixture; the actual OpenSandbox
  // endpoint and host permissions are tested in dedicated native Docker CI.
  let mockCapabilities = "sandbox";
  await page.route("**/api/status",async route=>{
    const actual = await route.fetch();
    if(!actual.ok()) return route.fulfill({response:actual});
    const status = await actual.json();
    status.capabilities = {...status.capabilities,
      python_backend:"opensandbox", python:mockCapabilities==="sandbox",
      python_sandbox:mockCapabilities==="sandbox",
      python_setup_required:mockCapabilities!=="sandbox"};
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify(status)});
  });
  await page.reload({waitUntil:"domcontentloaded"});
  await waitForText(page,"#server-label","Studio");
  await page.locator("#settings-top").click();
  await waitForText(page,"#python-description","operator-configured OpenSandbox container");
  await page.screenshot({path:path.join(evidence,"05-sandbox-wording-fixture.png"),fullPage:true});
  observations.tests.sandbox_permission_copy_fixture = true;
  await page.locator('[data-close="settings"]').first().click();
  mockCapabilities = "blocked";
  await page.reload({waitUntil:"domcontentloaded"});
  await waitForText(page,"#server-label","Studio");
  await page.locator("#settings-top").click();
  await waitForText(page,"#python-description","will not fall back to the host");
  await page.screenshot({path:path.join(evidence,"06-recovery-blocked-wording-fixture.png"),fullPage:true});
  observations.tests.recovery_blocked_copy_fixture = true;

  const mobile = await browser.newContext({viewport:{width:390,height:844},
    isMobile:true,hasTouch:true,deviceScaleFactor:1});
  const mobilePage = await mobile.newPage();
  mobilePage.on("pageerror",e=>errors.push(e.message));
  await mobilePage.goto(base+"/studio/",{waitUntil:"domcontentloaded"});
  await waitForText(mobilePage,"#server-label","Studio");
  assert.equal(await mobilePage.locator("#menu-toggle").isVisible(),true);
  assert.equal(await mobilePage.locator("#message-input").isVisible(),true);
  const overflow = await mobilePage.evaluate(() =>
    document.documentElement.scrollWidth > window.innerWidth+2);
  assert.equal(overflow,false,"Unexpected horizontal mobile overflow");
  await mobilePage.screenshot({path:path.join(evidence,"07-mobile.png"),fullPage:true});
  observations.tests.mobile_render_and_layout = true;
  assert.deepEqual(errors,[],"Browser JavaScript errors detected");
  await writeFile(path.join(evidence,"acceptance.json"),JSON.stringify(observations,null,2)+"\n");
  console.log(JSON.stringify({rendered_browser_acceptance:"pass",
    tests:Object.keys(observations.tests),real_model:false,real_docker:false,
    evidence_directory:evidence}));
} catch(error) {
  observations.failure = String(error?.stack || error);
  await writeFile(path.join(evidence,"acceptance.json"),JSON.stringify(observations,null,2)+"\n");
  console.error(error);
  process.exitCode = 1;
} finally {
  await stop();
}
