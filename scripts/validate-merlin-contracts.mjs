#!/usr/bin/env node
/** Dependency-free critical guard for Merlin task and evidence receipt payloads. */
import fs from 'node:fs';
const args = process.argv.slice(2);
const kind = args[0], file = args[1];
if (!['task','receipt'].includes(kind) || !file) {
  console.error('Usage: node scripts/validate-merlin-contracts.mjs <task|receipt> <json-file>');
  process.exit(2);
}
let value;
try { value = JSON.parse(fs.readFileSync(file, 'utf8')); }
catch (error) { console.error('Invalid JSON: ' + error.message); process.exit(1); }
const errors = [];
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const required = (x, keys, label) => keys.forEach(k => { if (!(k in x)) errors.push(label + ' missing ' + k); });
const sha40 = x => typeof x === 'string' && /^[0-9a-f]{40}$/.test(x);
const sha64 = x => typeof x === 'string' && /^[0-9a-f]{64}$/.test(x);
if (!object(value)) errors.push('root must be an object');
else if (kind === 'task') {
  required(value, ['schema_version','task_id','project_id','operation','repository','source','budget','approval','acceptance'], 'task');
  if (value.schema_version !== '1.0') errors.push('schema_version must be 1.0');
  const ops = ['archive.intake','github.read_repository','github.read_pull_request','github.prepare_draft_pr','avrea.dispatch_allowlisted_workflow','avrea.collect_artifacts','cace.run_lean_qualification','research.register_public_source','engineering.capture_artifact'];
  if (!ops.includes(value.operation)) errors.push('operation is not allowlisted');
  if (!object(value.repository)) errors.push('repository must be an object');
  else { required(value.repository, ['owner','name','connection_alias'], 'repository'); if (!['Primary','MorgansCace'].includes(value.repository.connection_alias)) errors.push('repository.connection_alias is not allowlisted'); }
  if (!object(value.source) || !sha40(value.source.expected_head_sha)) errors.push('source.expected_head_sha must be a full lowercase 40-character SHA');
  if (!object(value.budget)) errors.push('budget must be an object');
  else { if (!Number.isInteger(value.budget.max_attempts) || value.budget.max_attempts < 1 || value.budget.max_attempts > 3) errors.push('budget.max_attempts must be 1..3'); if (!Number.isInteger(value.budget.timeout_seconds) || value.budget.timeout_seconds < 1 || value.budget.timeout_seconds > 86400) errors.push('budget.timeout_seconds is out of range'); }
  if (!object(value.approval) || typeof value.approval.required !== 'boolean') errors.push('approval.required must be boolean');
  if (!Array.isArray(value.acceptance) || value.acceptance.length === 0) errors.push('acceptance must be a non-empty array');
} else {
  required(value, ['receipt_version','task_id','workflow','workflow_version','repository','source_commit','provider','result','started_at','finished_at','commands','artifacts','limitations','approval'], 'receipt');
  if (value.receipt_version !== '1.0') errors.push('receipt_version must be 1.0');
  if (!sha40(value.source_commit)) errors.push('source_commit must be a full lowercase 40-character SHA');
  if (!['passed','failed','timed_out','not_run','quarantined'].includes(value.result)) errors.push('result is invalid');
  if (!Array.isArray(value.artifacts)) errors.push('artifacts must be an array');
  else value.artifacts.forEach((a, i) => { if (!object(a) || typeof a.path !== 'string' || !sha64(a.sha256) || !Number.isInteger(a.size_bytes) || a.size_bytes < 0) errors.push('artifacts[' + i + '] is invalid'); });
  if (!object(value.approval) || typeof value.approval.required !== 'boolean') errors.push('approval.required must be boolean');
}
if (errors.length) { console.error(errors.map(e => '- ' + e).join('\n')); process.exit(1); }
console.log(kind + ' contract guard passed: ' + file);
