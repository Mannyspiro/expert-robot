import {experiment} from './experiment.mjs';

const ROUTE='/v1/receipts/latest';
const POLICY='cloudflare-toy-observer-v1';
const MAX_PAYLOAD=4096;
function reply(value,status=200){
 return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
}
export function dayFromMs(ms){
 if(!Number.isFinite(ms)||ms<0)throw Error('invalid scheduled timestamp');
 return new Date(ms).toISOString().slice(0,10);
}
async function digest(text){const bytes=new TextEncoder().encode(text);const b=await crypto.subtle.digest('SHA-256',bytes);return Array.from(new Uint8Array(b),x=>x.toString(16).padStart(2,'0')).join('');}
export async function makeReceipt(day){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(Date.parse(day+'T00:00:00Z')))throw Error('invalid day');
 const evidence=experiment();
 const content={schema_version:1,mode:'offline_artifact_only',policy:POLICY,
   source:'fixed-js-toy-regression—not-repository-head',date_utc:day,
   evidence,external_network_used:false,cloudflare_role:'toy-regression-only',
   lean_kernel_checked:false,cace_certificate:false,
   scientific_truth_or_formal_verification_claimed:false,
   promotion_authorized:false,authority_expanded:false};
 const canonical=JSON.stringify(content);
 if(canonical.length>MAX_PAYLOAD)throw Error('receipt too large');
 return {receipt:content,sha256:await digest(canonical)};
}
function ledger(env){
 if(!env?.RESEARCH_LEDGER)throw Error('Durable Object binding absent');
 return env.RESEARCH_LEDGER.get(env.RESEARCH_LEDGER.idFromName('research-observer-v1'));
}
export class ResearchLedger{
 constructor(ctx){
   this.ctx=ctx;
   this.ctx.storage.sql.exec('CREATE TABLE IF NOT EXISTS receipts (day TEXT PRIMARY KEY, content TEXT NOT NULL, sha256 TEXT NOT NULL)');
 }
 async fetch(request){
   const u=new URL(request.url);
   if(request.method==='GET'&&u.pathname==='/latest'){
     const x=this.ctx.storage.sql.exec('SELECT day,content,sha256 FROM receipts ORDER BY day DESC LIMIT 1').toArray();
     if(!x.length)return reply({status:'no_completed_episode'},404);
     return reply({status:'stored',date_utc:x[0].day,sha256:x[0].sha256,receipt:JSON.parse(x[0].content)});
   }
   if(request.method==='POST'&&u.pathname==='/store'){
     if(request.headers.get('content-type')!=='application/json')return reply({error:'unsupported_media_type'},415);
     const raw=await request.text();
     if(raw.length>MAX_PAYLOAD+256)return reply({error:'body_too_large'},413);
     let event;try{event=JSON.parse(raw);}catch{return reply({error:'bad_json'},400);}
     const {receipt,sha256}=event??{};
     if(!receipt||receipt.policy!==POLICY||receipt.promotion_authorized!==false||
        receipt.authority_expanded!==false||receipt.lean_kernel_checked!==false||
        !/^\d{4}-\d{2}-\d{2}$/.test(receipt.date_utc||'')||
        receipt.mode!=='offline_artifact_only'||receipt.evidence?.route!=='reaction-conservation'
     )return reply({error:'invalid_receipt'},400);
     const canonical=JSON.stringify(receipt);
     if(await digest(canonical)!==sha256)return reply({error:'bad_digest'},400);
     const prev=this.ctx.storage.sql.exec('SELECT sha256 FROM receipts WHERE day=?',receipt.date_utc).toArray();
     if(prev.length){
       if(prev[0].sha256!==sha256)return reply({error:'immutable_day_conflict'},409);
       return reply({status:'already_stored',date_utc:receipt.date_utc,sha256});
     }
     this.ctx.storage.sql.exec('INSERT INTO receipts (day,content,sha256) VALUES (?,?,?)',receipt.date_utc,canonical,sha256);
     return reply({status:'stored',date_utc:receipt.date_utc,sha256},201);
   }
   return reply({error:'route_not_found'},404);
 }
}
export default {
 async fetch(request,env){
   try{
     const path=new URL(request.url).pathname;
     if(request.method!=='GET')return reply({error:'read_only'},405);
     if(path==='/health')return reply({service:'expert-robot-cloudflare-observer',role:'toy_regression_only',
       operations:['GET /health','GET /v1/receipts/latest'],
       no_external_network:true,authorizes_promotion:false,formal_proof:false});
     if(path===ROUTE){const resp=await ledger(env).fetch('https://internal/latest');return resp;}
     return reply({error:'route_not_found'},404);
   }catch{return reply({error:'service_unavailable'},503);}
 },
 async scheduled(controller,env){
   // No public HTTP endpoint can request computation or write receipts.
   if(controller.cron!=='23 16 * * *')throw Error('unapproved schedule');
   const day=dayFromMs(controller.scheduledTime);
   const event=await makeReceipt(day);
   const response=await ledger(env).fetch('https://internal/store',{
     method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(event)});
   if(response.status!==201&&response.status!==200)throw Error('research receipt storage failed');
   const report=await response.json();
   console.log(JSON.stringify({event:'toy_observer_complete',date_utc:day,sha256:report.sha256,status:report.status}));
 }
};
