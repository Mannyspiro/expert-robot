const $ = id => document.getElementById(id);
const palette = ["#ba9bff","#82dbc9","#edaf82","#92b1ff","#df90ce","#e5cf83","#80caed","#e396a4"];
const fields = {name:"name",gain:"gain",pan:"pan",offset:"offset","trim-start":"first","trim-end":"last",eq:"eq"};
let audio;
let tracks = [];
let selected = null;
let position = 0;
let playback = null;
let recording = null;
let busy = false;

const number = (value, min, max) => Math.min(max, Math.max(min, Number(value) || 0));
const masterGain = () => Number($("master").value) / 100;
const clipLength = track => track.last - track.first;
const length = () => Math.max(0, ...tracks.map(t => t.offset + clipLength(t)));
const visibleLength = () => Math.max(length(),1);
const message = text => { $("status").textContent = text; };
const time = seconds => {
  const ticks = Math.floor(seconds * 100);
  return String(Math.floor(ticks / 6000)) + ":" + String(Math.floor(ticks / 100) % 60).padStart(2,"0")
    + "." + String(ticks % 100).padStart(2,"0");
};
function context() {
  audio ??= new AudioContext({sampleRate:48000});
  return audio;
}
async function draft(blob,name,options={}) {
  const buffer = await context().decodeAudioData(await blob.arrayBuffer());
  if (buffer.duration>3600) throw new Error("Track exceeds the one-hour session limit.");
  const track = {id:crypto.randomUUID(),name:name.slice(0,60),gain:0,pan:0,eq:0,offset:0,
    first:0,last:buffer.duration,mute:false,solo:false,...options,blob,buffer};
  track.last = number(track.last,.01,buffer.duration);
  track.first = number(track.first,0,track.last-.01);
  return track;
}
function updateTransport() {
  $("clock").value = time(position);
  $("duration").textContent = "/ " + time(length()).split(".")[0];
  for(const line of document.querySelectorAll(".cursor")) line.style.left = (position/visibleLength()*100) + "%";
}
function wave(canvas,track,color) {
  const ctx = canvas.getContext("2d");
  const signal = track.buffer.getChannelData(0);
  const begin = Math.floor(track.first * track.buffer.sampleRate);
  const end = Math.floor(track.last * track.buffer.sampleRate);
  const height = canvas.height / 2;
  let peak = .015;
  for(let j=begin; j<end; j+=17) peak=Math.max(peak,Math.abs(signal[j]));
  ctx.strokeStyle = color;
  ctx.beginPath();
  for(let x=0; x<canvas.width; x++) {
    const start = begin + Math.floor((end-begin) * x/canvas.width);
    const stop = begin + Math.floor((end-begin) * (x+1)/canvas.width);
    let high = 0, low = 0;
    for(let j=start; j<stop; j+=Math.max(1,Math.floor((stop-start)/48))) {
      high=Math.max(high,signal[j]); low=Math.min(low,signal[j]);
    }
    ctx.moveTo(x+.5,height*(1-number(high/peak,0,1)*.9));
    ctx.lineTo(x+.5,height*(1+number(-low/peak,0,1)*.9));
  }
  ctx.stroke();
}
function node(tag,cls,text) {
  const element=document.createElement(tag);
  if(cls) element.className=cls;
  if(text) element.textContent=text;
  return element;
}
function seek(event) {
  if(recording) return;
  const rect = event.currentTarget.getBoundingClientRect();
  const next = number((event.clientX-rect.left)/Math.max(1,rect.width),0,1) * length();
  const resume = playback !== null;
  stop(false);
  position = next;
  updateTransport();
  if(resume) void play();
}
function stateButton(text,label,on,change) {
  const button = node("button","",text);
  button.setAttribute("aria-label",label);
  button.setAttribute("aria-pressed",String(on));
  button.addEventListener("click",change);
  return button;
}
function draw() {
  $("track-count").textContent=tracks.length+" "+(tracks.length===1?"track":"tracks");
  $("play").disabled = !tracks.length;
  $("export").disabled = !tracks.length;
  const duration=visibleLength();
  const ruler=$("ruler");
  ruler.replaceChildren();
  for(let i=0;i<10;i++) {
    const tick=node("label","",time(i*duration/10).split(".")[0]);
    tick.style.left=i*10+"%";
    ruler.append(tick);
  }
  ruler.append(node("div","cursor"));
  const board=$("tracks");
  board.replaceChildren();
  tracks.forEach((track,i)=>{
    const color=palette[i%palette.length];
    const row=node("div","track"+(track.id===selected?" selected":""));
    row.style.setProperty("--track",color);
    const control=node("div","control");
    const title=node("button","select",track.name);
    title.title=track.name;
    title.addEventListener("click",()=>{ selected=track.id; draw(); });
    const toggle=(key)=>{
      track[key]=!track[key];
      applyMix();
      draw();
    };
    control.append(title,stateButton("M","Mute "+track.name,track.mute,()=>toggle("mute")),
      stateButton("S","Solo "+track.name,track.solo,()=>toggle("solo")));
    const lane=node("div","lane");
    const clip=node("div","cue");
    clip.style.left=track.offset/duration*100+"%";
    clip.style.width=clipLength(track)/duration*100+"%";
    const art=node("canvas");
    art.width=640; art.height=44;
    art.setAttribute("aria-hidden","true");
    wave(art,track,color);
    clip.append(art); lane.append(clip,node("div","cursor"));
    lane.addEventListener("click",seek);
    row.append(control,lane);
    board.append(row);
  });
  if(!tracks.length) board.append(node("div","message","Your tracks and recorded takes will appear here."));
  const track=tracks.find(t=>t.id===selected);
  $("inspector").hidden=!track;
  $("empty-inspector").hidden=Boolean(track);
  if(track) {
    for(const [id,key] of Object.entries(fields)) $(id).value=track[key];
    $("trim-start").max=track.last;
    $("trim-end").max=track.buffer.duration;
  }
  updateTransport();
}
function sendLevels(parts,master,ctx) {
  const soloed=tracks.some(t=>t.solo);
  for(const [t,n] of parts) {
    n.level.gain.setValueAtTime(t.mute|| (soloed&&!t.solo)?0:10**(t.gain/20),ctx.currentTime);
    n.filter.gain.setValueAtTime(t.eq,ctx.currentTime);
    n.pan.pan.setValueAtTime(t.pan,ctx.currentTime);
  }
  master.gain.setValueAtTime(masterGain(),ctx.currentTime);
}
function graph(ctx,cursor,when) {
  const master=ctx.createGain();
  master.connect(ctx.destination);
  const parts=new Map();
  for(const track of tracks) {
    const starts=track.offset;
    const skip=Math.max(0,cursor-starts);
    const cut=clipLength(track)-skip;
    if(cut<=0) continue;
    const source=ctx.createBufferSource();
    source.buffer=track.buffer;
    const level=ctx.createGain();
    const filter=ctx.createBiquadFilter();
    filter.type="highshelf"; filter.frequency.value=2800;
    const pan=ctx.createStereoPanner();
    source.connect(filter).connect(level).connect(pan).connect(master);
    source.start(when+Math.max(0,starts-cursor),track.first+skip,cut);
    parts.set(track,{source,level,filter,pan});
  }
  sendLevels(parts,master,ctx);
  return {parts,master};
}
function applyMix() {
  if(playback) sendLevels(playback.parts,playback.master,context());
}
function stop(keep=true) {
  if(!playback) return;
  const active=playback;
  if(keep) position=number(active.origin+audio.currentTime-active.when,0,length());
  playback=null;
  cancelAnimationFrame(active.handle);
  for(const n of active.parts.values()) n.source.stop();
  active.master.disconnect();
  active.analyser.disconnect();
  $("peak").value=0;
  $("play").removeAttribute("aria-pressed");
  updateTransport();
}
async function play() {
  if(playback||!length()) return;
  await context().resume();
  if(playback) return;
  if(position>=length()) position=0;
  const when=audio.currentTime+.035;
  const mix=graph(audio,position,when);
  const analyser=audio.createAnalyser();
  analyser.fftSize=512;
  mix.master.disconnect();
  mix.master.connect(analyser).connect(audio.destination);
  const signal=new Float32Array(analyser.fftSize);
  const active={...mix,analyser,origin:position,when};
  playback=active;
  $("play").setAttribute("aria-pressed","true");
  const refresh=()=>{
    if(playback!==active) return;
    position=number(active.origin+audio.currentTime-active.when,0,length());
    analyser.getFloatTimeDomainData(signal);
    $("peak").value=Math.min(1,Math.max(...signal.map(Math.abs)));
    updateTransport();
    if(position>=length()) stop(false);
    else active.handle=requestAnimationFrame(refresh);
  };
  refresh();
}
function setBusy(value) {
  busy=value;
  for(const id of ["demo","import","save","export","add-pattern"]) $(id).disabled=value || (id==="export"&&!tracks.length);
}
async function change(label,action) {
  if(busy||recording) return;
  setBusy(true);
  try { await action(); }
  catch(err) { message(label+": "+err.message); }
  finally { setBusy(false); }
}
async function rec() {
  if(recording) {
    const active=recording;
    if(active.recorder.state!=="inactive") active.recorder.stop();
    stop();
    return;
  }
  if(busy) return;
  if(!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder) {
    message("Microphone recording needs browser support and HTTPS or localhost.");
    return;
  }
  let stream;
  setBusy(true);
  try {
    stream=await navigator.mediaDevices.getUserMedia({
      audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false}});
    stop();
    if(position>=length()&&length()) position=0;
    const from=position;
    const recorder=new MediaRecorder(stream);
    const clips=[];
    recorder.ondataavailable=e=>{if(e.data.size) clips.push(e.data);};
    recorder.onstop=async()=>{
      stream.getTracks().forEach(track=>track.stop());
      recording=null;
      $("record").removeAttribute("aria-pressed");
      try{
        const blob=new Blob(clips,{type:recorder.mimeType});
        const track=await draft(blob,"Mic take "+(tracks.length+1),{offset:from});
        tracks.push(track);
        selected=track.id;
        draw();
        message("Microphone take added.");
      }catch(err){message("Could not load the take: "+err.message);}
      finally{setBusy(false);}
    };
    recorder.start();
    recording={recorder};
    $("record").setAttribute("aria-pressed","true");
    message("Recording microphone. Press Stop to finish.");
    if(tracks.length) await play();
  }catch(err){
    if(recording) recording.recorder.stop();
    else stream?.getTracks().forEach(track=>track.stop());
    setBusy(false);
    message("Microphone unavailable: "+err.message);
  }
}
function wav(buffer) {
  const size=buffer.length*4;
  const file=new ArrayBuffer(44+size);
  const view=new DataView(file);
  const str=(at,value)=>{for(let i=0;i<value.length;i++)view.setUint8(at+i,value.charCodeAt(i));};
  const num=(at,n)=>view.setUint32(at,n,true);
  str(0,"RIFF");num(4,36+size);str(8,"WAVEfmt ");num(16,16);
  view.setUint16(20,1,true);view.setUint16(22,2,true);
  num(24,buffer.sampleRate);num(28,buffer.sampleRate*4);
  view.setUint16(32,4,true);view.setUint16(34,16,true);str(36,"data");num(40,size);
  const left=buffer.getChannelData(0),right=buffer.getChannelData(1);
  let clipped=0;
  for(let i=0;i<buffer.length;i++) {
    if(Math.abs(left[i])>1||Math.abs(right[i])>1) clipped++;
    view.setInt16(44+i*4,Math.round(number(left[i],-1,1)*32767),true);
    view.setInt16(46+i*4,Math.round(number(right[i],-1,1)*32767),true);
  }
  return {file,clipped};
}
async function exportMix() {
  const duration=length();
  if(duration>600) throw new Error("WAV export supports up to ten minutes per mix in this build.");
  const offline=new OfflineAudioContext(2,Math.ceil(duration*48000),48000);
  graph(offline,0,0);
  const {file,clipped}=wav(await offline.startRendering());
  const url=URL.createObjectURL(new Blob([file],{type:"audio/wav"}));
  const link=node("a");
  link.href=url; link.download="Violet_Relay_Mix.wav";
  link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
  message(clipped ? "WAV exported. "+clipped+" samples clipped. Lower the master and export again." : "Stereo 48 kHz WAV exported.");
}
async function pattern() {
  if(tracks.length>=32) throw new Error("This session supports 32 tracks.");
  const notes=$("notes").value.trim().split(/\s+/);
  if(!notes.length||notes.length>64||notes.some(n=>!["–","-"].includes(n)&&(!/^\d+$/.test(n)||Number(n)>127))) {
    throw new Error("Enter one to 64 MIDI note numbers (0–127) or dashes for rests.");
  }
  const patch=$("patch").value;
  const definitions={keys:["sine",.025,.45],pluck:["triangle",.006,.18],
    bass:["triangle",.025,.13],pad:["sine",.12,.55]};
  const [type,attack,release]=definitions[patch];
  const step=60/number($("tempo").value,40,240)*Number($("steps").value);
  const ctx=new OfflineAudioContext(2,Math.ceil((notes.length*step+release)*48000),48000);
  notes.forEach((value,index)=>{
    if(["–","-"].includes(value)) return;
    const note=Number(value);
    const start=index*step;
    const length=step*.8;
    const level=ctx.createGain();
    level.gain.setValueAtTime(0,start);
    level.gain.linearRampToValueAtTime(.18,start+Math.min(attack,length*.55));
    level.gain.exponentialRampToValueAtTime(.036,start+length);
    level.gain.exponentialRampToValueAtTime(.001,start+length+release);
    level.connect(ctx.destination);
    for(const detune of (patch==="pad"?[-7,7]:[0])){
      const tone=ctx.createOscillator();
      tone.type=type;
      tone.frequency.value=440*2**((note-(patch==="bass"?12:0)-69)/12);
      tone.detune.value=detune;
      tone.connect(level);
      tone.start(start);
      tone.stop(start+length+release);
    }
  });
  const {file}=wav(await ctx.startRendering());
  const title=$("patch").selectedOptions[0].textContent;
  const track=await draft(new Blob([file],{type:"audio/wav"}),title,{offset:position});
  tracks.push(track);
  selected=track.id;
  draw();
  message(title+" pattern rendered.");
}
$("instrument").addEventListener("submit",event=>{
  event.preventDefault();
  void change("Instrument",pattern);
});
function database() {
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open("violet-relay-studio",1);
    request.onupgradeneeded=()=>request.result.createObjectStore("session");
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(request.error);
  });
}
async function session(write) {
  const db=await database();
  return new Promise((resolve,reject)=>{
    const transaction=db.transaction("session",write?"readwrite":"readonly");
    const table=transaction.objectStore("session");
    const request=write ? table.put({master:$("master").value,tracks:tracks.map(({buffer,...track})=>track)},"main") : table.get("main");
    transaction.oncomplete=()=>{ db.close(); resolve(request.result); };
    transaction.onabort=()=>{ db.close(); reject(transaction.error||new Error("Session operation stopped.")); };
  });
}
async function demo() {
  stop(false);
  const resp=await fetch("demo.json");
  if(!resp.ok) throw new Error("The demo assets are missing. Use the complete studio kit.");
  const list=await resp.json();
  const loaded=[];
  for(const item of list) {
    const asset=await fetch(item.url);
    if(!asset.ok) throw new Error("Could not load "+item.name);
    loaded.push(await draft(await asset.blob(),item.name));
  }
  tracks=loaded;
  position=0;
  selected=tracks[0]?.id;
  draw();
  message("Loaded Two Ways Out.");
}
$("ruler").addEventListener("click",seek);
document.addEventListener("keydown",e=>{
  if(e.code==="Space"&&!e.repeat&&e.target===document.body&&!recording){
    e.preventDefault();
    if(playback) stop();
    else void play().catch(err=>message(err.message));
  }
});
$("demo").addEventListener("click",()=>void change("Demo",demo));
$("play").addEventListener("click",()=>void play().catch(err=>message(err.message)));
$("stop").addEventListener("click",()=>{if(recording) void rec();else stop();});
$("rewind").addEventListener("click",()=>{if(!recording){stop(false);position=0;updateTransport();}});
$("record").addEventListener("click",()=>void rec());
$("master").addEventListener("input",applyMix);
$("inspector").addEventListener("submit",e=>e.preventDefault());
$("remove").addEventListener("click",()=>{
  if(recording||busy) return;
  stop(); tracks=tracks.filter(t=>t.id!==selected); selected=null;
  position=Math.min(position,length()); draw();
});
for(const [id,key] of Object.entries(fields)) $(id).addEventListener("change",()=>{
  if(recording||busy) return;
  const t=tracks.find(t=>t.id===selected);
  if(!t) return;
  const input=$(id);
  if(key==="name") t.name=input.value.trim().slice(0,60)||"Untitled track";
  else if(key==="first"||key==="last"||key==="offset") {
    stop();
    if(key==="first") t.first=number(input.value,0,t.last-.01);
    else if(key==="last") t.last=number(input.value,t.first+.01,t.buffer.duration);
    else t.offset=number(input.value,0,3600);
    position=Math.min(position,length());
  }else{
    t[key]=number(input.value,Number(input.min),Number(input.max));
    applyMix();
  }
  draw();
});
$("import").addEventListener("change",()=>void change("Import",async()=>{
  const input=$("import");
  const loading=[];
  try{
    for(const file of input.files) loading.push(await draft(file,file.name.replace(/\.[^.]+$/,"")));
    if(tracks.length+loading.length>32) throw new Error("This session supports 32 tracks.");
    tracks.push(...loading);
    selected=tracks.at(-1)?.id;
    draw();
    message(loading.length+" audio tracks imported.");
  }finally{input.value="";}
}));
$("save").addEventListener("click",()=>void change("Save",async()=>{
  await session(true);
  message("Session saved in this browser.");
}));
$("export").addEventListener("click",()=>void change("Export",exportMix));
draw();
void change("Session",async()=>{
  const stored=await session(false);
  if(stored?.tracks?.length){
    const restored=[];
    for(const {blob,name,...options} of stored.tracks) restored.push(await draft(blob,name,options));
    tracks=restored;
    $("master").value=stored.master;
    selected=tracks[0].id;
    draw();
    message("Restored the last saved session.");
  }
});
void fetch("chip-study.json").then(r=>r.ok?r.json():null).then(study=>{
  if(!study?.ranking?.length) return;
  const winner=study.ranking[0];
  $("chip-summary").textContent="Top modeled layout: "+winner.name+". Playback runs in your browser.";
  for(const [name,value] of [["Quantum",study.preferred_quantum+" samples"],["Peak modeled load",winner.worst_load_percent+"%"],["Working SRAM",winner.scratch_kib+" KiB"]]){
    $("chip-stats").append(node("dt","",name),node("dd","",value));
  }
}).catch(()=>{});
