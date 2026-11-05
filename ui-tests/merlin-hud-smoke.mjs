import assert from "node:assert/strict";
import { chromium } from "playwright";

const target = process.argv[2];
assert.ok(target, "deployment URL argument is required");
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
const pageErrors = [];
const nonReadRequests = [];
page.on("pageerror", error => pageErrors.push(String(error)));
page.on("request", request => {
  if (!["GET", "HEAD"].includes(request.method())) nonReadRequests.push(request.method() + " " + request.url());
});

const nodes = [
  { node_id: "cad:1", node_type: "freecad_model", label: "CAD assembly", payload: { parts: [{ name: "Test block", size_mm: [10, 12, 14], position_mm: [0, 0, 0] }] }, evidence_class: "unreviewed", source_uri: null },
  { node_id: "electrical:1", node_type: "electrical_net", label: "Divider wiring", payload: { components: [{ ref: "R1", name: "Resistor", x: 120, y: 90 }], nets: [] }, evidence_class: "unreviewed", source_uri: null },
  { node_id: "simulation:1", node_type: "simulation_result", label: "Simulation plot", payload: { series: [{ name: "Voltage", points: [{ x: 0, y: 0 }, { x: 1, y: 2.5 }] }] }, evidence_class: "unreviewed", source_uri: null }
];
const graph = {
  schema_version: "1.0",
  nodes,
  edges: [],
  snapshot_sha256: "ui-smoke-fixture",
  epistemic_notice: "Synthetic UI fixture only; not research evidence."
};
const workspace = {
  "cad:1": { schema: "merlin-hud-workspace/1", workspace: "freecad", title: "FreeCAD model", cad: { parts: nodes[0].payload.parts } },
  "electrical:1": { schema: "merlin-hud-workspace/1", workspace: "electrical", title: "Electrical net", netlist: { components: nodes[1].payload.components, nets: [] } },
  "simulation:1": { schema: "merlin-hud-workspace/1", workspace: "simulation", title: "Simulation", simulation: { series: nodes[2].payload.series } }
};
await page.route("**/api/hud/graph", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(graph) }));
await page.route("**/api/hud/node?*", async route => {
  const id = new URL(route.request().url()).searchParams.get("node_id");
  const node = nodes.find(item => item.node_id === id);
  if (!node) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ error: "node_not_found" }) });
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ node, neighbors: [], workspace: workspace[id], linked_artifacts: [] }) });
});

try {
  await page.goto(target, { waitUntil: "domcontentloaded", timeout: 30000 });
  await page.getByText("MERLIN", { exact: false }).first().waitFor({ state: "visible" });
  await page.waitForFunction(() => document.querySelector("#connection")?.textContent?.includes("LIVE EVENT FEED"), { timeout: 15000 });

  await page.locator("#graphReset").click();
  await page.locator("#graphReload").click();

  await page.locator('g[data-node="cad:1"]').click();
  await page.locator("#domainWorkspace [data-cad-scene] svg").waitFor({ state: "visible" });
  await page.locator("[data-cad-reset]").click();
  const cadSvg = await page.locator("#domainWorkspace [data-cad-scene] svg").count();
  assert.equal(cadSvg, 1, "CAD mesh preview should render");

  await page.locator('g[data-node="electrical:1"]').click();
  await page.locator('[data-electrical-node="R1"]').waitFor({ state: "visible" });
  await page.locator('[data-electrical-node="R1"]').click();
  await page.locator('[data-electrical-node="R1"].active').waitFor({ state: "visible" });

  await page.locator('g[data-node="simulation:1"]').click();
  await page.locator('[data-series="0"]').waitFor({ state: "visible" });
  await page.locator('[data-series="0"]').click();
  await page.locator('[data-series="0"].active').waitFor({ state: "visible" });

  await page.locator("#prompt").fill("browser smoke prompt");
  await page.locator("#chatForm button[type=submit]").click();
  await page.waitForFunction(() => document.querySelector("#chatNote")?.textContent?.includes("Chat endpoint not connected"));
  await page.locator("#mic").click();
  await page.locator("#attach").click();
  await page.waitForFunction(() => document.querySelector("#chatNote")?.textContent?.includes("Context attachment requires"));

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  assert.equal(overflow, false, "mobile layout should not overflow horizontally");
  assert.deepEqual(nonReadRequests, [], "read-only HUD must not issue non-GET requests");
  assert.deepEqual(pageErrors, [], "browser page should have no uncaught JavaScript errors");
  console.log(JSON.stringify({
    status: "PASS",
    checks: ["live activity", "3D graph controls", "FreeCAD preview", "electrical node selection", "simulation series selection", "chat fallback", "voice fallback", "attachment fallback", "mobile width", "read-only request policy"],
    synthetic_fixture_only: true,
    non_read_requests: nonReadRequests.length,
    page_errors: pageErrors.length
  }, null, 2));
} finally {
  await browser.close();
}
