/* Executable rendering/stream-state contracts. No browser or model is simulated. */
const fs=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../portable/merlin_studio/web/index.html'),'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script);
class Node {
  constructor(tag,text=''){this.tag=tag;this.text=text;this.children=[];this.attrs={};}
  append(...children){this.children.push(...children);}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(){}
}
const context={URL,TextEncoder,document:{createTextNode:s=>new Node('#text',s)},element:(tag,cls,text)=>{const n=new Node(tag,text===undefined?'':String(text));n.className=cls;return n;},display:x=>String(x),navigator:{},toast:()=>{},setTimeout:()=>{},state:{run:{events:[],status:'running'},streamOrdinal:0},terminal:new Set(['completed','failed','cancelled','interrupted']),scheduleRunRender:()=>{},recordedEvents:()=>context.state.run.events};
vm.createContext(context);
function source(start,end){return script.slice(script.indexOf(start),script.indexOf(end,script.indexOf(start)));}
vm.runInContext(source('  function appendInline(', '  function renderConversation('),context);
vm.runInContext(source('  function receiveRunEvent(', '  async function readRunStream('),context);
vm.runInContext(source('  function draftFromEvents(', '  function renderDraft('),context);
const nodes=n=>[n,...n.children.flatMap(nodes)];
const text=n=>n.text+n.children.map(text).join('');
const render=value=>{const root=new Node('root');context.appendContent(root,value);return root;};
const results=[];
function check(name,fn){fn();results.push({name,passed:true});}
check('Markdown headings lists tables and emphasis become structured text',()=>{
 const root=render('# Result\n\n**Verified** and *measured*.\n\n- First\n- Second\n\n| Mode | Bytes |\n| --- | ---: |\n| CPU | 42 |');
 assert.deepEqual(nodes(root).filter(n=>['h2','strong','em','ul','li','table','thead','tbody','th','td'].includes(n.tag)).map(n=>n.tag),['h2','strong','em','ul','li','li','table','thead','th','th','tbody','td','td']);
 assert.ok(text(root).includes('Verified and measured.'));
});
check('Model-provided HTML is literal text and cannot introduce active nodes',()=>{
 const payload='<script>alert(1)</script><img src=x onerror=alert(2)><iframe src=https://example.com></iframe>';
 const root=render(payload);assert.equal(text(root),payload);assert.equal(nodes(root).filter(n=>['script','img','iframe'].includes(n.tag)).length,0);
});
check('Links reject script data and embedded credentials while preserving safe sources',()=>{
 const root=render('[unsafe](javascript:evil) [data](data:text/html,x) [credential](https://user:pass@example.com/) [source](https://example.org/paper)');
 const links=nodes(root).filter(n=>n.tag==='a');assert.equal(links.length,1);assert.equal(links[0].href,'https://example.org/paper');assert.equal(links[0].rel,'noopener noreferrer');assert.equal(links[0].target,'_blank');
});
check('Fenced code retains literal markup and never parses links or emphasis',()=>{
 const value='<img src=x> **raw** [x](https://example.org/)';const root=render('```html\n'+value+'\n```');const code=nodes(root).find(n=>n.tag==='code');assert.equal(text(code),value);assert.equal(nodes(root).filter(n=>['img','a','strong'].includes(n.tag)).length,0);
});
check('Persisted stream cursors suppress duplicates and reject malformed deltas',()=>{
 context.state.run={events:[],status:'running'};context.state.streamOrdinal=0;
 context.receiveRunEvent({id:'a',ordinal:7,type:'text_delta',content:'café',step:1},7);
 context.receiveRunEvent({id:'a',ordinal:7,type:'text_delta',content:'café',step:1},7);
 context.receiveRunEvent({id:'old',ordinal:3,type:'text_delta',content:'old',step:1},3);
 assert.equal(context.state.run.events.length,1);assert.equal(context.state.streamOrdinal,7);
 assert.throws(()=>context.receiveRunEvent({id:'b',ordinal:8,type:'text_delta',content:{}},8));
 assert.throws(()=>context.receiveRunEvent({id:'b',ordinal:8,type:'text_delta',content:'x'},9));
 assert.equal(context.state.run.events.length,1);
});
check('Current response drafts close on model_response and retain cancellation as partial',()=>{
 context.state.conversation={id:'conversation'};context.state.run={conversation_id:'conversation',status:'running',events:[{type:'model_request',step:1},{type:'text_delta',step:1,content:'First '},{type:'text_delta',step:1,content:'part'}]};
 assert.equal(context.draftFromEvents().content,'First part');assert.equal(context.draftFromEvents().partial,false);
 context.state.run.status='cancelled';assert.equal(context.draftFromEvents().partial,true);
 context.state.run.events.push({type:'model_response',step:1,content:'First part'});assert.equal(context.draftFromEvents(),null);
 context.state.run.status='running';context.state.run.events.push({type:'model_request',step:2},{type:'text_delta',step:2,content:'Next'});assert.equal(context.draftFromEvents().content,'Next');
});
console.log(JSON.stringify({schema:'merlin-studio-web-contract/1',passed:results.length,results}));
