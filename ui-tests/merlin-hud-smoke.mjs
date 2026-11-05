import assert from "node:assert/strict";
import { chromium } from "playwright";

const target = process.argv[2];
assert.ok(target, "deployment URL argument is required");
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
const pageErrors = [];
const forbiddenRequests = [];
page.on("pageerror", error => pageErrors.push(String(error)));
page.on("request", request => {
  if (request.method() === "GET" || request.method() === "HEAD") return;
  const pathname = new URL(request.url()).pathname;
  if (!(request.method() === "POST" && pathname === "/api/council/prepare")) {
    forbiddenRequests.push(request.method() + " " + pathname);
  }
});

try {
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText("MERLIN", { exact: false }).first().waitFor({ state: "visible" });
  await page.waitForFunction(() => document.querySelector("#connection")?.textContent?.includes("LIVE EVENT FEED"), null, { timeout: 15000 });

  const graph = await page.evaluate(async () => {
    const response = await fetch("/api/hud/graph", { cache: "no-store" });
    if (!response.ok) throw new Error("graph endpoint returned " + response.status);
    return response.json();
  });
  assert.equal(graph.schema_version, "1.0");
  assert.ok(graph.nodes.length >= 5, "registered evidence graph should contain source, project, CAD, wiring, simulation and artifacts");
  const findNode = type => graph.nodes.find(node => node.node_type === type);
  const cad = findNode("freecad_assembly") || findNode("freecad_model");
  const electrical = findNode("electrical_net");
  const simulation = findNode("simulation_result");
  assert.ok(cad, "FreeCAD assembly node should be present");
  assert.ok(electrical, "electrical netlist node should be present");
  assert.ok(simulation, "ngspice result node should be present");

  await page.locator("#graphReset").click();
  await page.locator("#graphReload").click();

  await page.locator('g[data-node="' + cad.node_id + '"]').click();
  await page.locator("#domainWorkspace [data-cad-scene] svg").waitFor({ state: "visible" });
  await page.locator("[data-cad-reset]").click();
  assert.ok(await page.locator("#domainWorkspace [data-cad-scene] svg polygon, #domainWorkspace [data-cad-scene] svg path").count() > 0, "FreeCAD mesh preview should contain geometry");

  await page.locator('g[data-node="' + electrical.node_id + '"]').click();
  await page.locator("[data-electrical-scene] svg").waitFor({ state: "visible" });
  const electricalNode = page.locator("[data-electrical-node]").first();
  await electricalNode.waitFor({ state: "visible" });
  await electricalNode.click();

  await page.locator('g[data-node="' + simulation.node_id + '"]').click();
  await page.locator("[data-simulation-scene] svg").waitFor({ state: "visible" });
  await page.locator('[data-series="0"]').click();
  await page.locator("[data-simulation-scene] circle.chart-point").waitFor({ state: "visible" });

  await page.locator('[data-view="council"]').click();
  await page.locator("#prompt").fill("Browser qualification only: identify assumptions and falsifiers for a speculative engineering hypothesis.");
  await page.locator("#chatForm button[type=submit]").click();
  await page.waitForFunction(() => document.querySelectorAll(".council-card").length === 6, null, { timeout: 10000 });
  await page.getByText("No model responses or approvals were generated.", { exact: false }).waitFor({ state: "visible" });

  await page.locator('[data-view="capabilities"]').click();
  await page.locator(".capability-card").first().waitFor({ state: "visible" });
  await page.getByText("Code generation", { exact: true }).waitFor({ state: "visible" });
  await page.getByText("Video generation", { exact: true }).waitFor({ state: "visible" });

  await page.locator('[data-view="graph"]').click();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  assert.equal(overflow, false, "mobile layout should not overflow horizontally");
  assert.deepEqual(forbiddenRequests, [], "the browser must not invoke worker, code-execution or promotion endpoints");
  assert.deepEqual(pageErrors, [], "browser page should have no uncaught JavaScript errors");
  console.log(JSON.stringify({
    status: "PASS",
    checks: [
      "live activity feed",
      "canonical evidence graph",
      "FreeCAD mesh preview and reset",
      "electrical connectivity view and selection",
      "single-point ngspice operating-point visualization",
      "six-role skeptic council packet preparation",
      "capability readiness and explicit unavailable states",
      "mobile layout",
      "no unapproved write or execution endpoints",
      "no uncaught browser errors"
    ],
    graph_nodes: graph.nodes.length,
    graph_edges: graph.edges.length,
    forbidden_requests: forbiddenRequests.length,
    page_errors: pageErrors.length
  }, null, 2));
} finally {
  await browser.close();
}
