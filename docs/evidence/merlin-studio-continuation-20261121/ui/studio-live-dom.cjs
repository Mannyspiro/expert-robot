/* Actual Studio HTTP backend + actual UI JavaScript with a minimal DOM test double.
 * The DOM double does not establish rendered layout, browser security, or model quality.
 */
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path'),os=require('os');
const {spawn}=require('child_process');
const baseDir='/workspace/scratch/e6b5ba62b1d9';
const sourceDir=path.join(baseDir,'expert-robot/portable/merlin_studio');
const source=fs.readFileSync(path.join(sourceDir,'web/index.html'),'utf8');
const stateDir=fs.mkdtempSync(path.join(os.tmpdir(),'merlin-ui-live-'));
let processHandle=null,baseURL='';

class Node {
  constructor(tag='div',attrs={}){this.tagName=tag.toUpperCase();this.attrs=attrs;this.children=[];this.parentNode=null;this.listeners={};this.dataset={};this.style={};this.value=attrs.value||'';this.hidden='hidden' in attrs;this.disabled='disabled' in attrs;this.checked=false;this.scrollTop=0;this.scrollHeight=500;this.clientHeight=400;this._text='';for(const [k,v] of Object.entries(attrs)){if(k.startsWith('data-'))this.dataset[k.slice(5)]=v;}this.className=attrs.class||'';this.classList={add:(...x)=>this.className=[...new Set([...this.className.split(/\s+/),...x])].join(' ').trim(),remove:(...x)=>this.className=this.className.split(/\s+/).filter(i=>!x.includes(i)).join(' '),contains:x=>this.className.split(/\s+/).includes(x),toggle:(x,on)=>{on=on===undefined?!this.classList.contains(x):on;on?this.classList.add(x):this.classList.remove(x);return on}};}
  set textContent(v){this._text=String(v);this.children=[]}get textContent(){return this._text+this.children.map(x=>x.textContent).join('')}
  append(...nodes){for(let n of nodes){if(typeof n==='string'){const t=new Node('#text');t.textContent=n;n=t}n.parentNode=this;this.children.push(n)}}
  replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes)}
  setAttribute(k,v){this.attrs[k]=String(v);if(k==='class')this.className=String(v)}getAttribute(k){return this.attrs[k]}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn)}async click(){for(const fn of this.listeners.click||[])await fn({target:this,preventDefault(){}})}
  focus(){document.activeElement=this}remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(n=>n!==this)}
  get offsetParent(){let n=this;while(n){if(n.hidden)return null;n=n.parentNode}return this.parentNode||this}
  matches(sel){if(sel.includes(','))return sel.split(',').some(s=>this.matches(s.trim()));if(sel.startsWith('.'))return this.classList.contains(sel.slice(1));if(sel.startsWith('#'))return this.attrs.id===sel.slice(1);const m=/^\[([^=\]]+)(?:="([^"]*)")?\]$/.exec(sel);if(m)return m[1] in this.attrs&&(m[2]===undefined||this.attrs[m[1]]===m[2]);return this.tagName===sel.toUpperCase()}
  querySelectorAll(sel){const r=[];for(const c of this.children){if(c.matches(sel))r.push(c);r.push(...c.querySelectorAll(sel))}return r}
  querySelector(sel){return this.querySelectorAll(sel)[0]||null}
}
const document=new Node('document');document.activeElement=null;document.getElementById=id=>document.querySelector('#'+id);document.createElement=tag=>new Node(tag);document.createElementNS=(_,tag)=>new Node(tag);document.createTextNode=text=>{let n=new Node('#text');n.textContent=text;return n};document.hidden=false;
let stack=[document];const clean=source.replace(/<style>[\s\S]*?<\/style>/,'').replace(/<script>[\s\S]*?<\/script>/,'');
for(const match of clean.matchAll(/<\/?([\w-]+)([^>]*)>|([^<]+)/g)){if(match[3]){stack.at(-1).append(document.createTextNode(match[3]));continue;}if(match[0].startsWith('</')){if(stack.length>1)stack.pop();continue;}const attrs={};for(const a of match[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g))attrs[a[1]]=a[2]??'';const node=new Node(match[1],attrs);stack.at(-1).append(node);if(!['meta','input','br','hr','link','use','path','circle','rect','ellipse'].includes(match[1])&&!match[0].endsWith('/>'))stack.push(node);}
const ids={};for(const e of document.querySelectorAll('[id]'))ids[e.attrs.id]=e;document.getElementById=id=>ids[id]||null;
const saved=new Map(),timeouts=new Map(),requests=[];let timer=0;
const sandbox={document,fetch:async(relative,options={})=>{requests.push({path:relative,method:options.method||'GET',hasToken:Boolean(options.headers?.['X-Merlin-Token'])});return fetch(baseURL+relative,{...options,headers:{...options.headers,Origin:baseURL}})},navigator:{platform:'Linux',clipboard:{writeText:async()=>{}}},localStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)},requestAnimationFrame:f=>f(),setTimeout:(f,n)=>{timeouts.set(++timer,{f,n});return timer},clearTimeout:id=>timeouts.delete(id),confirm:()=>true,console,structuredClone,URL,Date,JSON,Set,Map,Error,Number,String,Boolean,Array,Object,Math};sandbox.window={addEventListener(){}};
let script=source.match(/<script>([\s\S]*)<\/script>/)[1];script=script.replace(/  boot\(\);\n\}\)\(\);/,'  globalThis.testUI={state,boot,openSettings,saveSettings,sendMessage,pollRun,openWorkspace,openFile,saveFile,closeDialog,newConversation,renderConversation,renderActivity,selectConversation,updateComposer,cancelRun,offlineCommand};\n})();');
vm.runInNewContext(script,sandbox,{timeout:2000});const ui=sandbox.testUI;
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));

async function launchServer(){
  processHandle=spawn('python3',[path.join(sourceDir,'server.py'),'--port','0','--data-dir',stateDir],{cwd:sourceDir,env:{...process.env,MERLIN_MODEL_URL:'',MERLIN_MODEL_ID:''},stdio:['ignore','pipe','pipe']});
  let output='',err='';processHandle.stdout.on('data',v=>output+=v);processHandle.stderr.on('data',v=>err+=v);
  for(let i=0;i<80;i++){const match=output.match(/Merlin Studio: (http:\/\/127\.0\.0\.1:\d+)/);if(match){baseURL=match[1];return}if(processHandle.exitCode!==null)throw Error('Server exited: '+err);await wait(50)}
  throw Error('Server startup timeout: '+err);
}
async function stopServer(hard=false){if(!processHandle||processHandle.exitCode!==null)return;const child=processHandle;child.kill(hard?'SIGKILL':'SIGTERM');for(let i=0;i<80&&child.exitCode===null&&child.signalCode===null;i++)await wait(50);if(child.exitCode===null&&child.signalCode===null)child.kill('SIGKILL');}
async function waitRun(expected){for(let i=0;i<100;i++){await ui.pollRun();if(expected.includes(ui.state.run?.status))return ui.state.run;await wait(50)}throw Error('Run did not reach '+expected+': '+JSON.stringify(ui.state.run));}
async function command(text,expected=['completed']){ids['message-input'].value=text;ui.updateComposer();assert(!ids['send-button'].disabled,'Offline command must be enabled: '+text);await ui.sendMessage();return waitRun(expected);}

(async()=>{
  const checks=[];let browserResult={scope:'not attempted'};
  try{
    await launchServer();
    const livePage=await fetch(baseURL+'/studio/');assert(livePage.ok);assert((await livePage.text()).includes('Try /help'));checks.push('actual HTTP serves current HTML');
    try{
      const {chromium}=require('playwright');const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
      try{const page=await browser.newPage({viewport:{width:1440,height:1000}});await page.goto(baseURL+'/studio/');await page.locator('#offline-help').waitFor();await page.screenshot({path:path.join(baseDir,'ui-qa/live-welcome.png')});browserResult={scope:'actual backend rendered',passed:true};}finally{await browser.close()}
    }catch(error){browserResult={scope:'render unavailable',passed:false,error:String(error.message).includes('socket() failed')?'Chromium Unix socket() denied before page startup':String(error.message).slice(0,700)};}
    await ui.boot();assert(!ui.state.connectionFailed);assert(ui.state.status.model.configured===false);assert(ui.offlineCommand('/help'));assert(ids['max-steps'].attrs.max==='12');checks.push('live status/token and offline command discovery');
    await command('/help');assert(ids.messages.textContent.includes('These commands work without a language model'));checks.push('model-free /help through actual UI and backend');
    await command('/write notes/idea.md\nLive UI integration note');assert(ui.state.run.status==='completed');
    await command('/read notes/idea.md');assert(ids.messages.textContent.includes('Live UI integration note'));checks.push('model-free /write and /read persist through canonical backend');
    await ui.openWorkspace();await ui.openFile('notes/idea.md');assert(ids['file-content'].value==='Live UI integration note');ids['file-content'].value='Edited through the UI';ui.state.editorDirty=true;await ui.saveFile({preventDefault(){}});assert(!ui.state.editorDirty);assert(fs.readFileSync(path.join(stateDir,'workspace/notes/idea.md'),'utf8')==='Edited through the UI');ui.closeDialog('workspace');checks.push('actual workspace editor save');
    await command('/write answer.py\nprint(6 * 7)');await command('/python answer.py',['waiting_approval']);assert(ids.messages.textContent.includes('script_sha256'));assert(ids.messages.textContent.includes('local user’s permissions'));
    const approve=ids.messages.querySelectorAll('button').find(x=>x.textContent==='Approve once');assert(approve);await approve.click();await waitRun(['completed','failed']);assert(ui.state.run.status==='completed',ui.state.run.error);assert(ids.messages.textContent.includes('42'));checks.push('bound script approval and actual Python 42 result');
    await command('/python answer.py',['waiting_approval']);await ui.cancelRun();await waitRun(['cancelled']);assert(ids.messages.textContent.includes('This run was stopped'));checks.push('cancel waiting approval through actual endpoint');
    await ui.openSettings();ids['max-steps'].value='12';await ui.saveSettings(null,false);assert(ui.state.status.model.configured===false);checks.push('actual settings accepts UI maximum12');
    await command('/python answer.py',['waiting_approval']);const interruptedId=ui.state.runId;await stopServer(true);await launchServer();await ui.boot();assert(ui.state.runId===interruptedId);assert(ui.state.run.status==='interrupted');assert(ids.messages.textContent.includes('Server restarted'));assert(!saved.get('merlin.run'));checks.push('hard restart restores interrupted run without replay or endless polling');
    ui.newConversation();assert(ui.state.conversation===null);assert(ids.welcome.hidden===false);checks.push('new chat available after interrupted recovery');
    assert(requests.filter(r=>r.method==='POST').every(r=>r.hasToken));checks.push('all real mutation requests carry local session token');
    const result={scope:'Actual UI JavaScript via DOM test double against real Studio HTTP server, SQLite/canonical registry, filesystem, Python subprocess and restart; no AI inference claimed',checks,browser:browserResult,requestCount:requests.length,mutationCount:requests.filter(r=>r.method==='POST').length};
    fs.writeFileSync(path.join(baseDir,'ui-qa/live-ui-result.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));
  }finally{await stopServer();fs.rmSync(stateDir,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1});
