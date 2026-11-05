const DATA_URL="./science-map.json";
let data=null, filter="all", query="";
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function render(){
 const domains=data.domains.filter(d=>(filter==="all"||d.status===filter)&&(!query||[d.name,...d.branches].join(" ").toLowerCase().includes(query)));
 $("#domains").innerHTML=domains.length?domains.map(d=>`<article class="domain"><span class="tag">${esc(d.status.replaceAll("_"," "))}</span><h3>${esc(d.name)}</h3><p>${d.branches.length} branches and research topics</p><div class="chips">${d.branches.slice(0,5).map(x=>`<span class="chip">${esc(x)}</span>`).join("")}${d.branches.length>5?'<span class="chip">+'+(d.branches.length-5)+' more</span>':""}</div></article>`).join(""):'<div class="empty">No matching fields. Try another search or filter.</div>';
 $("#count").textContent=`${domains.length} of ${data.domains.length} fields`;
}
function renderFilters(){
 const vals=[["all","All"],["established","Established"],["interdisciplinary","Interdisciplinary"],["emerging","Emerging / speculative"]];
 $("#filters").innerHTML=vals.map(([v,l])=>`<button class="filter ${filter===v?"active":""}" data-filter="${v}">${l}</button>`).join("");
 $("#filters").querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{filter=b.dataset.filter;renderFilters();render()}));
}
function renderHistory(){ $("#history-grid").innerHTML=data.historical_programs.map(h=>`<article class="history"><span class="tag">${esc(h.status.replaceAll("_"," "))}</span><h3>${esc(h.label)}</h3><p>${esc(h.lesson)}</p></article>`).join("");}
function renderSources(){ $("#sources-grid").innerHTML=data.sources.map(s=>`<article class="source"><h3>${esc(s.name)}</h3><p>${esc(s.kind)} · ${esc(s.access)}</p><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open collection ↗</a></article>`).join("");}
function renderReading(){ $("#reading-grid").innerHTML=(data.reading_list||[]).map(b=>`<article class="source"><span class="tag">${esc(b.date)}</span><h3>${esc(b.title)}</h3><p><b>${esc(b.creator)}</b></p><p>${esc(b.context)}</p><p><i>Read with:</i> ${esc(b.questions.join(" · "))}</p><a href="${esc(b.url)}" target="_blank" rel="noopener noreferrer">Open verified public-domain record ↗</a></article>`).join("");}
function renderFuture(){const d=data.domains.find(x=>x.id==="emerging");$("#future-list").innerHTML=d.branches.map(x=>`<span>${esc(x)}</span>`).join("");}
fetch(DATA_URL).then(r=>{if(!r.ok)throw new Error("map unavailable");return r.json()}).then(d=>{data=d;$("#q").addEventListener("input",e=>{query=e.target.value.trim().toLowerCase();render()});renderFilters();render();renderHistory();renderSources();renderReading();renderFuture()}).catch(()=>{$("#count").textContent="Map data unavailable";$("#domains").innerHTML='<div class="empty">The atlas data could not be loaded. Check the deployment bundle.</div>'});
