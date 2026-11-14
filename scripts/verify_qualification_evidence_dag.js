#!/usr/bin/env node
"use strict";

// Independent Node.js verifier for Merlin qualification DAG v1 canonical
// identities, graph structure, and snapshot digest. No Python imports or
// shared implementation code are used.
const crypto = require("node:crypto");
const fs = require("node:fs");

const NODE_TYPES = new Set([
  "source_commit", "artifact_version", "workflow_run", "cace_attestation",
  "trust_root", "verification_receipt", "oci_execution",
  "protected_orchestrator", "lean_compile",
]);
const RELATIONS = new Set([
  "derived_from", "built_by", "attests", "verifies", "executes", "qualifies",
]);
const STATUSES = new Set([
  "qualified", "unqualified", "stale", "revoked", "blocked",
]);

function compareCodePoints(left, right) {
  const a = Array.from(left, ch => ch.codePointAt(0));
  const b = Array.from(right, ch => ch.codePointAt(0));
  const length = Math.min(a.length, b.length);
  for (let i = 0; i < length; i += 1) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

function validateJson(value, path = "$") {
  if (value === null || typeof value === "string" || typeof value === "boolean") return;
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) {
      throw new Error(`non-integer or unsafe JSON number at ${path}`);
    }
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => validateJson(item, `${path}[${index}]`));
    return;
  }
  if (typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype) {
    for (const [key, item] of Object.entries(value)) {
      validateJson(item, `${path}.${key}`);
    }
    return;
  }
  throw new Error(`unsupported JSON value at ${path}`);
}

function canonical(value) {
  validateJson(value);
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  const keys = Object.keys(value).sort(compareCodePoints);
  return `{${keys.map(key => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
}

function sha256(value) {
  return crypto.createHash("sha256").update(value, "utf8").digest("hex");
}

function exactKeys(value, expected, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  const actual = Object.keys(value).sort(compareCodePoints);
  const wanted = [...expected].sort(compareCodePoints);
  if (canonical(actual) !== canonical(wanted)) {
    throw new Error(`${label} has missing or unexpected fields`);
  }
}

function requireDigest(value, label) {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/.test(value)) {
    throw new Error(`${label} is not a lowercase SHA-256 digest`);
  }
}

function verify(snapshot) {
  exactKeys(snapshot, ["schema", "authority", "nodes", "edges", "snapshot_sha256"], "snapshot");
  if (snapshot.schema !== "merlin-qualification-evidence-dag/1"
      || snapshot.authority !== "read-only-projection") {
    throw new Error("unsupported snapshot schema or authority");
  }
  if (!Array.isArray(snapshot.nodes) || !Array.isArray(snapshot.edges)) {
    throw new Error("snapshot nodes and edges must be arrays");
  }

  const nodes = [...snapshot.nodes];
  const nodeIds = new Set();
  for (const node of nodes) {
    exactKeys(node, [
      "node_id", "node_type", "identity", "record_sha256", "evidence_class", "status",
    ], "node");
    if (!NODE_TYPES.has(node.node_type)) throw new Error("unknown node type");
    if (!node.identity || typeof node.identity !== "object" || Array.isArray(node.identity)
        || Object.keys(node.identity).length === 0) throw new Error("invalid node identity");
    if (node.node_id !== `sha256:${sha256(canonical({
      node_type: node.node_type, identity: node.identity,
    }))}`) throw new Error("node identity digest mismatch");
    requireDigest(node.record_sha256, "record_sha256");
    if (typeof node.evidence_class !== "string" || node.evidence_class.length < 1
        || node.evidence_class.length > 128) throw new Error("invalid evidence class");
    if (!STATUSES.has(node.status)) throw new Error("unknown node status");
    if (nodeIds.has(node.node_id)) throw new Error("duplicate node identity");
    nodeIds.add(node.node_id);
  }

  const edges = [...snapshot.edges];
  const edgeKeys = new Set();
  const indegree = new Map([...nodeIds].map(id => [id, 0]));
  const dependents = new Map([...nodeIds].map(id => [id, new Set()]));
  for (const edge of edges) {
    exactKeys(edge, ["dependent_node_id", "prerequisite_node_id", "relation"], "edge");
    const { dependent_node_id: dependent, prerequisite_node_id: prerequisite, relation } = edge;
    if (!/^sha256:[0-9a-f]{64}$/.test(dependent)
        || !/^sha256:[0-9a-f]{64}$/.test(prerequisite)) throw new Error("invalid edge node ID");
    if (!RELATIONS.has(relation)) throw new Error("unknown edge relation");
    if (dependent === prerequisite) throw new Error("self-dependency");
    if (!nodeIds.has(dependent) || !nodeIds.has(prerequisite)) throw new Error("unknown edge endpoint");
    const edgeKey = canonical([dependent, prerequisite, relation]);
    if (edgeKeys.has(edgeKey)) throw new Error("duplicate evidence edge");
    edgeKeys.add(edgeKey);
    if (!dependents.get(prerequisite).has(dependent)) {
      dependents.get(prerequisite).add(dependent);
      indegree.set(dependent, indegree.get(dependent) + 1);
    }
  }

  const ready = [...nodeIds].filter(id => indegree.get(id) === 0).sort(compareCodePoints);
  let visited = 0;
  while (ready.length) {
    const prerequisite = ready.shift();
    visited += 1;
    const next = [...dependents.get(prerequisite)].sort(compareCodePoints);
    for (const dependent of next) {
      indegree.set(dependent, indegree.get(dependent) - 1);
      if (indegree.get(dependent) === 0) {
        ready.push(dependent);
        ready.sort(compareCodePoints);
      }
    }
  }
  if (visited !== nodeIds.size) throw new Error("evidence dependency graph contains a cycle");

  nodes.sort((a, b) => compareCodePoints(a.node_id, b.node_id));
  edges.sort((a, b) => compareCodePoints(
    canonical([a.dependent_node_id, a.prerequisite_node_id, a.relation]),
    canonical([b.dependent_node_id, b.prerequisite_node_id, b.relation]),
  ));
  const normalized = {
    schema: snapshot.schema,
    authority: snapshot.authority,
    nodes,
    edges,
  };
  requireDigest(snapshot.snapshot_sha256, "snapshot_sha256");
  const computed = sha256(canonical(normalized));
  if (computed !== snapshot.snapshot_sha256) throw new Error("snapshot SHA-256 mismatch");
  return {
    status: "verified",
    snapshot_sha256: computed,
    node_count: nodes.length,
    edge_count: edges.length,
  };
}

try {
  const raw = fs.readFileSync(0, "utf8");
  const snapshot = JSON.parse(raw);
  if (raw !== canonical(snapshot)) throw new Error("input is not canonical JSON");
  process.stdout.write(JSON.stringify(verify(snapshot)) + "\n");
} catch (error) {
  process.stderr.write(String(error && error.message ? error.message : error) + "\n");
  process.exitCode = 1;
}
