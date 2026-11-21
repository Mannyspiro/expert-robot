/* UI-only fixture acceptance. No model, Python, desktop, or real network tool runs. */
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const assert=require('assert');

(async()=>{
  const root='/workspace/scratch/e6b5ba62b1d9';
  const output=path.join(root,'ui-qa');
  fs.mkdirSync(output,{recursive:true});
  const html=fs.readFileSync(path.join(root,'expert-robot/portable/merlin_studio/web/index.html'),'utf8');
  const browser=await chromium.launch({executablePath:process.env.MERLIN_TEST_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
  try {
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const page=await context.newPage();
    const errors=[];const requests=[];
    let settings={model_url:'',model_id:'local',network_enabled:false,python_enabled:true,desktop_enabled:false,max_steps:8};
    let conversations=[],conversation=null,run=null;
    const files={'notes/idea.md':'# A good question\nWhat would change our minds?'};
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('http://127.0.0.1:8771/**',async route=>{
      const req=route.request();const pathname=new URL(req.url()).pathname;
      const body=req.method()==='POST'?req.postDataJSON():{};let data={};
      if(req.method()==='POST')requests.push({path:pathname,token:req.headers()['x-merlin-token'],body});
      if(pathname==='/')return route.fulfill({status:200,contentType:'text/html',body:html});
      if(pathname==='/api/status')data={ready:true,version:'0.2.0-fixture',model:{configured:!!settings.model_url,reachable:!!settings.model_url,model_id:settings.model_id,endpoint:settings.model_url},capabilities:{workspace:true,python:true,python_sandbox:false,network:settings.network_enabled,browser:false,desktop:false,desktop_installed:false,research_transport:'public_https'},workspace:'/fixture/merlin/workspace',session_token:'fixture-token',setup_required:!settings.model_url};
      else if(pathname==='/api/settings'){if(req.method()==='POST')settings={...settings,...body};data={settings,models:[]};}
      else if(pathname==='/api/model/probe')data={reachable:true,models:[{id:'local-model'}]};
      else if(pathname==='/api/conversations'&&req.method()==='GET')data={conversations};
      else if(pathname==='/api/conversations'){conversation={id:'c1',title:body.title||'New conversation',messages:[],events:[]};conversations=[conversation];data={conversation};}
      else if(pathname==='/api/conversations/c1')data={conversation};
      else if(pathname==='/api/chat'){conversation.messages.push({id:'m1',role:'user',content:body.message,created_at:new Date().toISOString()});run={id:'r1',status:'waiting_approval',events:[{id:'e1',type:'tool_call',tool:'run_python',arguments:{path:'test.py'},created_at:new Date().toISOString()}],pending_approval:{id:'a1',tool:'run_python',arguments:{path:'test.py'}}};data={run_id:'r1'};}
      else if(pathname==='/api/runs/r1')data={run,conversation};
      else if(pathname==='/api/runs/r1/approve'){run.status='completed';delete run.pending_approval;run.events.push({id:'e2',type:'tool_result',tool:'run_python',result:{exit_code:0,stdout:'42'}});conversation.messages.push({id:'m2',role:'assistant',content:'The result is `42`.\n\n```python\nprint(6 * 7)\n```\n\n<img src=x onerror="window.hacked=true">',created_at:new Date().toISOString()});data={accepted:true};}
      else if(pathname==='/api/workspace'){const folder=new URL(req.url()).searchParams.get('path');data={path:folder,files:folder==='.'?[{name:'notes',path:'notes',directory:true}]:Object.keys(files).filter(p=>p.startsWith('notes/')).map(p=>({name:p.split('/').pop(),path:p,directory:false,size:files[p].length}))};}
      else if(pathname==='/api/tool'){if(body.tool==='read_file')data={result:{content:files[body.args.path]}};else{files[body.args.path]=body.args.content;data={result:{written:body.args.path}};}}
      else return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({error:'Not found: '+pathname})});
      await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
    });
    await page.goto('http://127.0.0.1:8771/');
    await page.getByText('Connect a model to start chatting').waitFor();
    await page.screenshot({path:path.join(output,'welcome-desktop.png'),fullPage:true});
    assert(!(await page.locator('#send-button').isEnabled()),'Send requires a model');
    await page.locator('#setup-button').click();
    await page.locator('#model-url').fill('http://127.0.0.1:8080/v1/chat/completions');
    await page.locator('#probe-button').click();
    await page.getByText('Connection successful.',{exact:false}).waitFor();
    await page.locator('#model-id').fill('local-model');
    await page.locator('#save-settings').click();
    await page.locator('#message-input').fill('Write a small calculation and run it.');
    await page.locator('#send-button').click();
    await page.getByRole('button',{name:'Approve once'}).waitFor();
    await page.locator('#activity-toggle').click();
    await page.screenshot({path:path.join(output,'approval-desktop.png'),fullPage:true});
    await page.getByRole('button',{name:'Approve once'}).click();
    await page.getByText('The result is',{exact:false}).waitFor();
    assert(!(await page.evaluate(()=>!!window.hacked)),'Model HTML remains text');
    await page.locator('#workspace-nav').click();
    await page.locator('.file-item').filter({hasText:'notes'}).click();
    await page.locator('.file-item').filter({hasText:'idea.md'}).click();
    await page.locator('#file-content').fill('Updated note');
    await page.locator('#save-file').click();
    await page.getByText('Saved notes/idea.md',{exact:true}).waitFor();
    assert.equal(files['notes/idea.md'],'Updated note');
    await page.locator('[data-close="workspace"]').last().click();
    await page.reload();
    await page.locator('#messages .message.assistant').waitFor();
    await page.screenshot({path:path.join(output,'chat-desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    if(await page.locator('#activity-close').isVisible())await page.locator('#activity-close').click();
    await page.screenshot({path:path.join(output,'chat-mobile.png'),fullPage:true});
    const layout=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth,app:document.getElementById('app').scrollWidth}));
    assert(layout.document<=layout.viewport,'No mobile horizontal overflow');
    assert(requests.every(r=>r.token==='fixture-token'),'Mutations use session token');
    assert.deepEqual(errors,[],'No browser errors');
    console.log(JSON.stringify({scope:'fixture-driven UI interactions; no real inference or tool execution',checks:['no-model setup','save/probe settings','create chat','poll approval','approve once','tool activity','safe text/code rendering','workspace editing','conversation reload','responsive mobile','mutation token'],mutationRequests:requests.length,browserErrors:errors,layout},null,2));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
