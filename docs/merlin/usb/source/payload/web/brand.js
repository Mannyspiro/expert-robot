const $ = id=>document.getElementById(id);
const ascii=$("ascii");
const menu=$("launcher");
const launch=$("launch");
const audioSwitch=$("sounds");
let audioContext, sound=localStorage.getItem("merlin_chimes")==="on";
const reduce=matchMedia("(prefers-reduced-motion: reduce)");
const letters={
 M:["#   #","## ##","# # #","#   #","#   #"],
 E:["#####","#    ","#### ","#    ","#####"],
 R:["#### ","#   #","#### ","#  # ","#   #"],
 L:["#    ","#    ","#    ","#    ","#####"],
 I:["#####","  #  ","  #  ","  #  ","#####"],
 N:["#   #","##  #","# # #","#  ##","#   #"]
};
const field=Array.from({length:10},()=>Array(35).fill(" "));
[..."MERLIN"].forEach((letter,i)=>letters[letter].forEach((row,j)=>[...row].forEach((c,k)=>{
 if(c!==" ")field[i+j][i*6+k]=c;
})));
ascii.textContent=field.map(row=>row.join("").trimEnd()).join("\n");
function syncSound(){
 audioSwitch.setAttribute("aria-pressed",String(sound));
 audioSwitch.textContent=sound?"Chimes on":"Chimes off";
}
function soundEngine(){
 if(!sound)return;
 const Audio=window.AudioContext||window.webkitAudioContext;
 if(!Audio)return;
 audioContext??=new Audio();
 if(audioContext.state==="suspended")audioContext.resume().catch(()=>{});
 return audioContext;
}
function chime(kind){
 const ctx=soundEngine();
 if(!ctx||ctx.state!=="running")return;
 const notes=kind==="sent"?[392,588]:kind==="fault"?[329.63,246.94]:[523.25,659.25,783.99];
 notes.forEach((note,i)=>{
  const t=ctx.currentTime+.015+i*.08,osc=ctx.createOscillator(),gain=ctx.createGain();
  osc.type="sine";osc.frequency.value=note;gain.gain.setValueAtTime(.0001,t);
  gain.gain.exponentialRampToValueAtTime(.036,t+.028);
  gain.gain.exponentialRampToValueAtTime(.0001,t+.16);
  osc.connect(gain);gain.connect(ctx.destination);osc.start(t);osc.stop(t+.17);
 });
 $("sound-status").textContent=kind+" chime";
}
window.merlinSignal=kind=>{
 if(kind==="sent"&&!reduce.matches){
  ascii.animate([{transform:"rotateY(0deg) rotate(-6deg)"},{transform:"rotateY(90deg) rotate(-6deg)",opacity:.25},
   {transform:"rotateY(0deg) rotate(-6deg)"}],{duration:660,easing:"ease-in-out"});
 }
 chime(kind);
};
audioSwitch.addEventListener("click",()=>{
 sound=!sound;localStorage.setItem("merlin_chimes",sound?"on":"off");syncSound();
 if(sound){const ctx=soundEngine();if(ctx)ctx.resume().then(()=>chime("ready")).catch(()=>{});}
});
function toggle(open){menu.hidden=!open;launch.setAttribute("aria-expanded",String(open));}
launch.addEventListener("click",()=>toggle(menu.hidden));
menu.querySelectorAll("a").forEach(link=>link.addEventListener("click",()=>toggle(false)));
document.addEventListener("keydown",event=>{if(event.key==="Escape"&&!menu.hidden){toggle(false);launch.focus();}});
function clock(){$("clock").textContent=new Date().toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"});}
clock();setInterval(clock,15000);syncSound();
