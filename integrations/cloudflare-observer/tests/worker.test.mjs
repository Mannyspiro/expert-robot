import test from 'node:test';
import assert from 'node:assert/strict';
import worker, {ResearchLedger,makeReceipt,dayFromMs} from '../src/worker.mjs';
import {experiment} from '../src/experiment.mjs';
class SqlMock{
 constructor(){this.rows=new Map();}
 exec(sql,...args){
   if(sql.startsWith('CREATE TABLE'))return {toArray:()=>[]};
   if(sql.startsWith('SELECT day,content'))return {toArray:()=>[...this.rows].sort((a,b)=>b[0].localeCompare(a[0])).slice(0,1).map(([day,r])=>({day,...r}))};
   if(sql.startsWith('SELECT sha256'))return {toArray:()=>this.rows.has(args[0])?[{sha256:this.rows.get(args[0]).sha256}]:[]};
   if(sql.startsWith('INSERT INTO')){this.rows.set(args[0],{content:args[1],sha256:args[2]});return {toArray:()=>[]};}
   throw Error('unexpected SQL');
 }
}
const db=new SqlMock();const obj=new ResearchLedger({storage:{sql:db}});
const env={RESEARCH_LEDGER:{idFromName:name=>name,get:()=>({fetch:(url,options)=>obj.fetch(new Request(url,options))})}};
const json=async r=>r.json();
test('four exact-rational cases + deterministic mutation controls',()=>{
 const x=experiment();assert.equal(x.case_count,4);
 assert.deepEqual(x.left_nullities,[2,1,2,1]);
 assert.ok(x.residuals.length>=6&&x.residuals.every(v=>v==='0'));
 assert.equal(x.missing_reactant_mass_defect,'1/3');
 assert.equal(x.formal_lean_verified,false);
 assert.equal(x.production_promotion_authorized,false);
});
test('deterministic source-described receipt',async()=>{
 const a=await makeReceipt('2026-10-10'),b=await makeReceipt('2026-10-10');
 assert.deepEqual(a,b);assert.match(a.sha256,/^[0-9a-f]{64}$/);
 assert.equal(a.receipt.source,'fixed-js-toy-regression—not-repository-head');
 assert.equal(a.receipt.authority_expanded,false);
});
test('public read-only API has no writing or scheduling endpoint',async()=>{
 assert.equal((await worker.fetch(new Request('https://example/health'),env)).status,200);
 for(const path of ['/v1/receipts/latest','/store','/scheduled','/../store']){
  const response=await worker.fetch(new Request('https://example'+path,{method:'POST'}),env);
  assert.equal(response.status,405,path);
 }
 assert.equal((await worker.fetch(new Request('https://example/unknown'),env)).status,404);
 assert.equal((await worker.fetch(new Request('https://example/v1/receipts/latest'),{})).status,503);
});
test('scheduled event persisted once, is immutable, and is retrievable',async()=>{
 const time=Date.parse('2026-10-11T16:23:00Z');
 assert.equal(dayFromMs(time),'2026-10-11');
 await worker.scheduled({cron:'23 16 * * *',scheduledTime:time},env);
 const first=await json(await worker.fetch(new Request('https://example/v1/receipts/latest'),env));
 assert.equal(first.status,'stored');assert.equal(first.receipt.date_utc,'2026-10-11');
 const original=first.sha256;
 await worker.scheduled({cron:'23 16 * * *',scheduledTime:time},env);
 assert.equal(db.rows.size,1);
 assert.equal((await json(await worker.fetch(new Request('https://example/v1/receipts/latest'),env))).sha256,original);
 const counterfeit={receipt:{...first.receipt,evidence:{...first.receipt.evidence,case_count:999}},sha256:original};
 const bad=await obj.fetch(new Request('https://internal/store',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(counterfeit)}));
 assert.equal(bad.status,400);
 const alternate=await makeReceipt('2026-10-11');alternate.receipt.source='alternative';
 const bytes=new TextEncoder().encode(JSON.stringify(alternate.receipt));
 const buff=await crypto.subtle.digest('SHA-256',bytes);
 alternate.sha256=[...new Uint8Array(buff)].map(x=>x.toString(16).padStart(2,'0')).join('');
 const conflict=await obj.fetch(new Request('https://internal/store',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(alternate)}));
 assert.equal(conflict.status,409);
});
test('bad schedules rejected before storage',async()=>{
 await assert.rejects(worker.scheduled({cron:'* * * * *',scheduledTime:Date.now()},env));
 assert.throws(()=>dayFromMs(-1));
});
