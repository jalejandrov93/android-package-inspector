let DATA = null, SORT = {key:"stars", dir:-1}, FILTER = "all", SEARCH = "";
const SELECTED = new Set();

const FILTERS = [
  ["all","Todas"],["user","Usuario"],["system","Sistema"],["bloatware","Bloatware"],
  ["overlay","Overlay"],["boot_completed","Boot"],["accessibility","Accessibility"],
  ["unknown","Installer ?"],["high","Alto"],["critical","Criticas"]
];

function stars(n){ return "★".repeat(n)+"☆".repeat(5-n); }

function matchesFilter(a){
  switch(FILTER){
    case "all": return true;
    case "user": return a.type==="user";
    case "system": return a.type==="system";
    case "overlay": return a.overlay;
    case "boot_completed": return a.boot_completed;
    case "accessibility": return a.accessibility;
    case "unknown": return a.installer_label==="Unknown" && a.type==="user";
    case "high": return a.stars>=4;
    case "critical": return a.critical;
    case "bloatware": return !!a.bloatware;
  }
}

function visibleApps(){
  let list = DATA.apps.filter(matchesFilter);
  if(SEARCH) list = list.filter(a=>a.package.toLowerCase().includes(SEARCH));
  const k = SORT.key;
  list.sort((x,y)=>{
    let vx=x[k], vy=y[k];
    if(k==="package"||k==="type"){ return SORT.dir*String(vx).localeCompare(String(vy)); }
    return SORT.dir*((vx||0)-(vy||0));
  });
  return list;
}

function flagChips(a){
  const f=[];
  if(a.bloatware) f.push(`<span class="flag bloat" title="${a.bloatware.description||''} (${a.bloatware.removal||''})">${a.bloatware.category||'bloat'}</span>`);
  if(a.critical) f.push(`<span class="flag hot">critica</span>`);
  if(a.overlay) f.push(`<span class="flag hot">overlay</span>`);
  if(a.accessibility) f.push(`<span class="flag hot">a11y</span>`);
  if(a.boot_completed) f.push(`<span class="flag">boot</span>`);
  if(a.device_admin) f.push(`<span class="flag hot">admin</span>`);
  if(a.foreground_service) f.push(`<span class="flag">fgsvc</span>`);
  if(a.internet) f.push(`<span class="flag">net</span>`);
  if(a.installer_label==="Unknown") f.push(`<span class="flag">inst?</span>`);
  if(a.frozen) f.push(`<span class="flag frozen">frozen</span>`);
  return `<div class="flags">${f.join("")}</div>`;
}

function groupKey(a){
  const g=document.getElementById("group").value;
  if(g==="risk") return a.stars>=4?"Alto riesgo":a.stars===3?"Medio":"Bajo";
  if(g==="type") return a.type==="system"?"Sistema":"Usuario";
  if(g==="installer") return a.installer_label||"Unknown";
  return null;
}

function render(){
  const list = visibleApps();
  const rows = document.getElementById("rows");
  rows.innerHTML="";
  let lastGroup=null;
  for(const a of list){
    const gk=groupKey(a);
    if(gk!==null && gk!==lastGroup){
      lastGroup=gk;
      const tr=document.createElement("tr"); tr.className="grouphdr";
      tr.innerHTML=`<td colspan="5">${gk}</td>`; rows.appendChild(tr);
    }
    const tr=document.createElement("tr");
    const col = a.stars>=4?"var(--red)":a.stars===3?"var(--amber)":"var(--muted)";
    const pct = Math.max(0, Math.min(100, a.score_pct||0));
    tr.innerHTML=`
      <td><input type="checkbox" data-pkg="${a.package}" ${SELECTED.has(a.package)?"checked":""} aria-label="Seleccionar ${a.package}"></td>
      <td><span class="stars" style="color:${col}" title="${a.score_pct}/100">${stars(a.stars)}</span><span class="scorebar" aria-hidden="true"><i style="width:${pct}%"></i></span></td>
      <td class="pkg">
        <div class="pkg-cell">
          <img class="app-icon" src="/api/icon/${encodeURIComponent(a.package)}" loading="lazy" alt="">
          <span title="${a.package}">${a.package}</span>
        </div>
      </td>
      <td><span class="badge ${a.type}">${a.type}</span></td>
      <td>${flagChips(a)}</td>`;
    tr.querySelector('input').addEventListener("change",e=>{
      e.target.checked?SELECTED.add(a.package):SELECTED.delete(a.package);
      updateSel();
    });
    tr.querySelectorAll("td").forEach((td,i)=>{ if(i>0) td.style.cursor="pointer";
      if(i>0) td.addEventListener("click",()=>openDrawer(a)); });
    rows.appendChild(tr);
  }
  const empty = document.getElementById("emptyState");
  if(empty) empty.style.display = list.length ? "none" : "flex";
  updateSel();
}

function updateSel(){
  document.getElementById("selcount").textContent=`${SELECTED.size} seleccionadas`;
  const sel=[...SELECTED].map(p=>DATA.apps.find(a=>a.package===p)).filter(Boolean);
  const hasSystem = sel.some(a=>a.type==="system");
  const isOffline = !!(DATA && DATA.offline);
  document.getElementById("btnUninstall").disabled = SELECTED.size===0 || hasSystem || isOffline;
  document.getElementById("btnUninstall").title = isOffline ?
    "Acciones deshabilitadas en modo offline" :
    (hasSystem ? "La selección incluye apps de sistema: solo se pueden congelar" : "");
  document.getElementById("btnFreeze").disabled = SELECTED.size===0 || isOffline;
  document.getElementById("btnFreeze").title = isOffline ? "Acciones deshabilitadas en modo offline" : "";
  document.getElementById("btnUnfreeze").disabled = SELECTED.size===0 || isOffline;
  document.getElementById("btnUnfreeze").title = isOffline ? "Acciones deshabilitadas en modo offline" : "";
}

function openDrawer(a){
  const d=document.getElementById("drawer");
  const perms=(a.dangerous_permissions||[]).map(p=>`<div class="perm">· ${p.split(".").pop()}</div>`).join("")||"<div>—</div>";
  const reasons=(a.reasons||[]).map(r=>`<li>${r}</li>`).join("")||"<li>—</li>";
  d.innerHTML=`
    <button class="btn xs ghost" onclick="closeAll()" style="float:right" aria-label="Cerrar detalle">Cerrar</button>
    <div class="drawer-hdr">
      <img class="drawer-icon" src="/api/icon/${encodeURIComponent(a.package)}" alt="">
      <div>
        <h2 style="margin:0 0 4px 0">${a.package}</h2>
        <div class="riskline"><span class="stars">${stars(a.stars)}</span> <b>${a.score_pct}/100</b>
          ${a.critical?`<span class="badge crit">${a.critical_reason||"critica"}</span>`:""}
          ${a.frozen?`<span class="badge user">frozen</span>`:""}</div>
      </div>
    </div>
    <div class="kv">
      <div>Tipo</div><div>${a.type}${a.frozen?" · frozen":""}</div>
      <div>Installer</div><div>${a.installer_label||"Unknown"}</div>
      <div>VersionName</div><div>${a.version_name||"—"}</div>
      <div>VersionCode</div><div>${a.version_code||"—"}</div>
      <div>UID</div><div>${a.uid||"—"}</div>
      <div>Instalada</div><div>${a.first_install_time||"—"}</div>
      <div>Actualizada</div><div>${a.last_update_time||"—"}</div>
      <div>APK</div><div class="pkg" style="word-break:break-all">${a.code_path||"—"}</div>
      <div>Firma (hash)</div><div class="pkg">${a.signature||"—"}</div>
      <div>Exported</div><div>act:${a.exported_activities||0} · svc:${a.exported_services||0} · rcv:${a.exported_receivers||0} · prov:${a.exported_providers||0}</div>
      ${a.bloatware?`<div>Bloatware</div><div>${a.bloatware.category} · <b>${a.bloatware.removal}</b><br><span class="stats">${a.bloatware.description||""}</span></div>`:""}
    </div>
    <h3>Permisos peligrosos</h3>${perms}
    <h3>Motivos del riesgo</h3><ul>${reasons}</ul>`;
  d.classList.add("open");
  document.getElementById("obg").classList.add("show");
}

function closeAll(){
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("modal").classList.remove("show");
  document.getElementById("wifiModal").classList.remove("show");
  document.getElementById("obg").classList.remove("show");
}

function toast(msg){
  const t=document.getElementById("toast"); t.textContent=msg; t.classList.add("show");
  setTimeout(()=>t.classList.remove("show"),2600);
}

// ---- live log helpers ----
function showLog(){ document.getElementById("logpanel").classList.add("show"); }
function logLine(msg, cls="info"){
  const b=document.getElementById("logbody");
  const d=document.createElement("div");
  d.className="logline "+cls; d.textContent=msg;
  b.appendChild(d); b.scrollTop=b.scrollHeight;
}
function logStatus(msg){ document.getElementById("logstatus").textContent=msg; }

// Read an NDJSON stream from a fetch Response, invoking onEvent per line.
async function readNdjson(res, onEvent){
  const reader=res.body.getReader(); const dec=new TextDecoder();
  let buf="";
  for(;;){
    const {value,done}=await reader.read();
    if(done) break;
    buf+=dec.decode(value,{stream:true});
    let nl;
    while((nl=buf.indexOf("\n"))>=0){
      const line=buf.slice(0,nl).trim(); buf=buf.slice(nl+1);
      if(line) onEvent(JSON.parse(line));
    }
  }
  if(buf.trim()) onEvent(JSON.parse(buf.trim()));
}

async function doAction(action, confirm=false){
  const packages=[...SELECTED];
  if(!packages.length) return;
  const LABELS={freeze:"Congelando",unfreeze:"Descongelando",uninstall:"Desinstalando"};
  const res=await fetch("/api/action",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({action,packages,confirm})});
  // Safety gate replies as JSON (not a stream).
  if(res.headers.get("Content-Type")?.includes("application/json")){
    const body=await res.json();
    if(res.status===403){ toast("Bloqueado: "+body.error); logLine("Bloqueado: "+body.error,"err"); showLog(); return; }
    if(res.status===409 && body.needs_confirm){ showConfirm(action, body); return; }
    toast("Error: "+(body.error||res.status)); return;
  }
  showLog();
  logLine("──────── "+(LABELS[action]||action)+" "+packages.length+" app(s) ────────","info");
  let ok=0;
  await readNdjson(res, evt=>{
    if(evt.type==="progress"){
      logLine(`[${evt.i}/${evt.n}] ${evt.ok?"OK":"ERROR"} ${evt.package} — ${evt.output||""}`, evt.ok?"ok":"err");
      if(evt.ok) ok++;
      logStatus(`${evt.i}/${evt.n}`);
    } else if(evt.type==="done"){
      logLine(`Listo: ${evt.ok}/${evt.total} OK`, evt.ok===evt.total?"ok":"err");
      logStatus("");
      toast(`${action}: ${evt.ok}/${evt.total} OK`);
    }
  });
  await refreshState();
}

// Fast post-action refresh: update frozen states and drop uninstalled apps,
// without a full re-scan.
async function refreshState(){
  const st=await(await fetch("/api/state")).json();
  const frozen=new Set(st.frozen), installed=new Set(st.installed);
  DATA.apps=DATA.apps.filter(a=>installed.has(a.package));
  DATA.apps.forEach(a=>{ a.frozen=frozen.has(a.package); });
  DATA.counts.total=DATA.apps.length;
  DATA.counts.user=DATA.apps.filter(a=>a.type==="user").length;
  DATA.counts.system=DATA.apps.filter(a=>a.type==="system").length;
  [...SELECTED].forEach(p=>{ if(!installed.has(p)) SELECTED.delete(p); });
  renderStats(); render();
}

function showConfirm(action, body){
  const m=document.getElementById("modal");
  const crit=body.critical.map(c=>`<li><b>${c.package}</b> — ${c.reason||"critica"}</li>`).join("");
  const cmds=body.commands.map(c=>`<div><code>adb shell ${c}</code></div>`).join("");
  m.innerHTML=`
    <h3>Confirmacion requerida</h3>
    <div class="warnbox">
      <b>La seleccion incluye apps criticas</b> (bancos / redes / mensajeria).
      Congelarlas o desinstalarlas puede romper accesos importantes:
      <ul>${crit}</ul>
    </div>
    <p>Se ejecutara:</p>${cmds}
    <div class="row">
      <button class="btn ghost" onclick="closeAll()">Cancelar</button>
      <button class="danger btn danger" onclick="closeAll();doAction('${action}',true)">
        Entiendo, continuar</button>
    </div>`;
  m.classList.add("show");
  document.getElementById("obg").classList.add("show");
}

function confirmUninstall(){
  const packages=[...SELECTED];
  const cmds=packages.map(p=>`<div><code>adb shell pm uninstall --user 0 ${p}</code></div>`).join("");
  const m=document.getElementById("modal");
  m.innerHTML=`
    <h3>Desinstalar ${packages.length} app(s)</h3>
    <div class="warnbox">Accion agresiva. Se ejecutara (por-usuario):</div>
    ${cmds}
    <div class="row">
      <button class="btn ghost" onclick="closeAll()">Cancelar</button>
      <button class="danger btn danger" onclick="closeAll();doAction('uninstall')">Desinstalar</button>
    </div>`;
  m.classList.add("show");
  document.getElementById("obg").classList.add("show");
}

function renderStats(){
  const c=DATA.counts;
  const off=document.getElementById("offlineBadge");
  if(off) off.style.display=DATA.offline?"inline-flex":"none";
  const nd=document.getElementById("noDeviceBadge");
  if(nd) nd.style.display=(!DATA.offline && DATA.no_device)?"inline-flex":"none";
  if(DATA.offline || DATA.no_device){
    const r=document.getElementById("rescan");
    if(r){ r.disabled=true;
      r.title=DATA.no_device?"Conecta un dispositivo por WiFi primero":"Rescan no disponible en modo offline"; }
    const s=document.getElementById("sysToggle"); if(s){ s.disabled=true; }
  }
  document.getElementById("stats").innerHTML=
    `${c.total} apps · ${c.user} usuario · ${c.system} sistema · `+
    `<span class="badge warn">${c.high_risk} alto</span> `+
    `<span class="badge crit">${c.critical} criticas</span> `+
    `<span class="badge sys">${c.bloatware||0} bloatware</span>`;
  const set = (id, v) => { const el=document.getElementById(id); if(el) el.textContent=v; };
  set("ovTotal", c.total ?? "—");
  set("ovHigh", c.high_risk ?? "—");
  set("ovCrit", c.critical ?? "—");
  set("ovBloat", c.bloatware ?? 0);
  set("ovSub", `${c.user ?? 0} usuario · ${c.system ?? 0} sistema`);
}

async function reload(keepSel=false){
  const res=await fetch("/api/apps"); DATA=await res.json();
  if(!keepSel) SELECTED.clear();
  renderStats();
  render();
}

function buildChips(){
  const c=document.getElementById("chips"); c.innerHTML="";
  for(const [key,label] of FILTERS){
    const b=document.createElement("button");
    b.className="chip"+(FILTER===key?" active":""); b.textContent=label;
    b.onclick=()=>{ FILTER=key; buildChips(); render(); };
    c.appendChild(b);
  }
}

document.getElementById("search").addEventListener("input",e=>{
  SEARCH=e.target.value.toLowerCase().trim(); render();
});
document.getElementById("group").addEventListener("change",render);
document.getElementById("selall").addEventListener("change",e=>{
  visibleApps().forEach(a=>e.target.checked?SELECTED.add(a.package):SELECTED.delete(a.package));
  render();
});
document.querySelectorAll("th[data-sort]").forEach(th=>{
  th.onclick=()=>{ const k=th.dataset.sort;
    SORT.dir = SORT.key===k? -SORT.dir : (k==="package"||k==="type"?1:-1);
    SORT.key=k; render(); };
});
document.getElementById("btnFreeze").onclick=()=>doAction("freeze");
document.getElementById("btnUnfreeze").onclick=()=>doAction("unfreeze");
document.getElementById("btnUninstall").onclick=confirmUninstall;
document.getElementById("obg").onclick=closeAll;

// log panel controls
document.getElementById("btnLog").onclick=()=>
  document.getElementById("logpanel").classList.toggle("show");
document.getElementById("logclose").onclick=()=>
  document.getElementById("logpanel").classList.remove("show");
document.getElementById("logclear").onclick=()=>
  document.getElementById("logbody").innerHTML="";

async function runRescan(){
  const includeSystem=document.getElementById("sysToggle").checked;
  const bar=document.getElementById("scanbar"), fill=document.getElementById("scanfill"),
        msg=document.getElementById("scanmsg");
  bar.style.display="block"; fill.style.width="0"; msg.textContent="Iniciando…";
  document.getElementById("rescan").disabled=true;
  const res=await fetch("/api/rescan",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({system:includeSystem})});
  await readNdjson(res, evt=>{
    if(evt.type==="progress"){
      const pct=Math.round(evt.i/evt.n*100);
      fill.style.width=pct+"%";
      msg.textContent=`Escaneando ${evt.i}/${evt.n} — ${evt.package}`;
    } else if(evt.type==="done"){
      DATA=evt.data; SELECTED.clear(); renderStats(); render();
      msg.textContent=`Listo: ${evt.data.counts.total} apps`;
    }
  });
  setTimeout(()=>{ bar.style.display="none"; },1200);
  document.getElementById("rescan").disabled=false;
}
document.getElementById("rescan").onclick=runRescan;
document.getElementById("sysToggle").onchange=runRescan;

document.getElementById("export").onclick=async()=>{
  await(await fetch("/api/export")).json();
  toast("Exportado: report.json + recommendations.txt");
};

// ---- WiFi / ADB inalámbrico ----
function wifiLog(msg, cls="info"){
  const el=document.getElementById("wifiLog");
  const d=document.createElement("div");
  d.className="logline "+cls; d.textContent=msg;
  el.appendChild(d); el.scrollTop=el.scrollHeight;
}
function switchTab(name){
  document.querySelectorAll("[data-wtab]").forEach(x=>
    x.classList.toggle("active", x.dataset.wtab===name));
  for(const t of ["ip","pair","discover"]){
    const el=document.getElementById("wtab-"+t);
    if(el) el.style.display = t===name?"block":"none";
  }
}
function openWifi(){
  document.getElementById("wifiModal").classList.add("show");
  document.getElementById("obg").classList.add("show");
  wifiStatus();
}
function closeWifi(){
  document.getElementById("wifiModal").classList.remove("show");
  document.getElementById("obg").classList.remove("show");
}
async function wifiStatus(){
  try{
    const j=await(await fetch("/api/device/status")).json();
    const note=document.getElementById("pairNote");
    if(!j.supports_pairing){
      note.textContent="Este adb no soporta pairing (requiere platform-tools 30+). "+
        "Usa 'IP directa' o actualiza adb.";
    }else{
      note.textContent="adb "+((j.adb&&j.adb.version)||"")+" · pairing disponible";
    }
    const dv=(j.devices||[]).map(d=>`${d.serial} [${d.state}]`).join(", ");
    wifiLog("Dispositivos: "+(dv||"ninguno"),"info");
  }catch(e){ wifiLog("No se pudo consultar el estado de adb: "+e,"err"); }
}
async function doWifiConnect(){
  const host=document.getElementById("wHost").value.trim();
  const port=document.getElementById("wPort").value.trim()||"5555";
  if(!host){ toast("Ingresa la IP del dispositivo"); return; }
  const b=document.getElementById("wConnectBtn");
  b.disabled=true; b.textContent="Conectando…";
  wifiLog(`> adb connect ${host}:${port}`,"info");
  try{
    const res=await fetch("/api/wifi/connect",{method:"POST",
      headers:{"Content-Type":"application/json"},body:JSON.stringify({host,port})});
    const j=await res.json();
    if(j.output) wifiLog(j.output, j.ok?"ok":"err");
    if(j.ok){
      toast("Conectado: "+(j.serial||host));
      closeWifi(); await runRescan();
    }else{
      toast("No se pudo conectar");
      wifiLog("Verifica la IP/puerto y que el teléfono esté en la misma red.","info");
    }
  }catch(e){ wifiLog("Error: "+e,"err"); toast("Error de conexión"); }
  b.disabled=false; b.textContent="Conectar";
}
async function doWifiPair(){
  const host=document.getElementById("pHost").value.trim();
  const port=document.getElementById("pPort").value.trim();
  const code=document.getElementById("pCode").value.trim();
  if(!host||!port||!code){ toast("Completa IP, puerto y código"); return; }
  const b=document.getElementById("wPairBtn");
  b.disabled=true; b.textContent="Vinculando…";
  wifiLog(`> adb pair ${host}:${port} ${code}`,"info");
  try{
    const res=await fetch("/api/wifi/pair",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({host,pairing_port:port,code})});
    const j=await res.json();
    if(j.output) wifiLog(j.output, j.ok?"ok":"err");
    if(j.ok){
      toast("Emparejado y conectado: "+(j.serial||host));
      closeWifi(); await runRescan();
    }else if(j.paired){
      wifiLog("Emparejado, pero no se autodetectó el puerto de conexión.","info");
      wifiLog("En la pantalla principal de Depuración inalámbrica verás 'IP y "+
              "puerto'; usa la pestaña 'IP directa' con ese puerto.","info");
      toast("Emparejado. Falta conectar.");
    }else{
      toast("No se pudo emparejar");
    }
  }catch(e){ wifiLog("Error: "+e,"err"); toast("Error de emparejamiento"); }
  b.disabled=false; b.textContent="Vincular";
}
async function doWifiDiscover(){
  const b=document.getElementById("wDiscoverBtn");
  const list=document.getElementById("discoveryList");
  b.disabled=true; b.textContent="Buscando…";
  try{
    const j=await(await fetch("/api/wifi/discover")).json();
    list.innerHTML="";
    if(!j.services||!j.services.length){
      list.textContent="Sin servicios mDNS detectados.";
    }else{
      for(const s of j.services){
        const row=document.createElement("div"); row.className="svc";
        const label=document.createElement("span"); label.className="pkg";
        label.textContent=`${s.name}  ${s.type}  ${s.address}${s.port?":"+s.port:""}`;
        const use=document.createElement("button"); use.textContent="usar";
        use.onclick=()=>{
          if((s.type||"").includes("pairing")){
            document.getElementById("pHost").value=s.address;
            document.getElementById("pPort").value=s.port||"";
            switchTab("pair"); toast("Datos de pairing cargados (falta el código)");
          }else{
            document.getElementById("wHost").value=s.address;
            document.getElementById("wPort").value=s.port||"5555";
            switchTab("ip"); toast("Datos de conexión cargados");
          }
        };
        row.appendChild(label); row.appendChild(use); list.appendChild(row);
      }
    }
  }catch(e){ list.textContent="Error: "+e; }
  b.disabled=false; b.textContent="Buscar servicios mDNS";
}

document.getElementById("btnWifi").onclick=openWifi;
document.getElementById("wConnectBtn").onclick=doWifiConnect;
document.getElementById("wPairBtn").onclick=doWifiPair;
document.getElementById("wDiscoverBtn").onclick=doWifiDiscover;
document.querySelectorAll("[data-wtab]").forEach(b=>b.onclick=()=>switchTab(b.dataset.wtab));

buildChips();
reload().then(()=>{
  if(DATA && (DATA.no_device || (DATA.counts && DATA.counts.total===0))) openWifi();
});
