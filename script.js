let apiConnected = false;

function getApiBase(){
  if(window.location.protocol.startsWith("http")) return window.location.origin;
  return "http://localhost:5000";
}

async function pingApi(){
  try{
    const r = await fetch(getApiBase()+"/api/health",{signal:AbortSignal.timeout(3000)});
    if(r.ok){
      apiConnected = true;
      document.getElementById("dropBadgeApi").style.display = "inline-block";
    } else throw new Error("status "+r.status);
  } catch(e){
    apiConnected = false;
    document.getElementById("dropBadgeApi").style.display = "none";
  }
}

window.addEventListener("load", ()=>{
  setTimeout(pingApi, 500);
  initColEditor();

  const drop = document.getElementById("drop");
  const fi = document.getElementById("fi");
  if (drop && fi) {
    drop.addEventListener("click", () => fi.click());
    fi.addEventListener("change", e => { if (e.target.files[0]) go(e.target.files[0]); fi.value = ""; });
    drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("over"));
    drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) go(e.dataTransfer.files[0]); });
  }
});

async function sendToApi(file){
  const fd = new FormData();
  fd.append("file",             file);
  fd.append("excel",            "true");
  fd.append("snowflake",        "true");
  fd.append("automate",         "true");
  fd.append("expected_columns", JSON.stringify(getExpectedCols()));
  fd.append("warehouse",        (document.getElementById("sfWarehouse").value || "").trim());
  fd.append("database",         (document.getElementById("sfDatabase").value || "").trim());
  fd.append("schema",           (document.getElementById("sfSchema").value || "").trim());
  fd.append("table",            (document.getElementById("sfTable").value || "").trim());

  try{
    const resp = await fetch(getApiBase()+"/api/process", {method:"POST", body:fd});
    const data = await resp.json();

    if(!data.success){
      showErr("Backend Error", data.error || "Unknown error from backend.");
      return null;
    }

    showOk(`Processed ${data.count} records.`);
    showOverdue(data.overdue || []);
    return data;

  } catch(e){
    showErr("Connection Error", "Could not reach Flask API.\n"+e.message);
    return null;
  }
}

function toggleSfPanel(){
  const el = document.getElementById("sfPanel");
  if(el.style.display === "none"){
    el.style.display = "block";
    loadSfOptions();
  } else {
    el.style.display = "none";
  }
}

function fillDatalist(id, items){
  const dl = document.getElementById(id);
  if(!dl) return;
  dl.innerHTML = (items || []).map(v => `<option value="${esc(v)}"></option>`).join("");
}

async function loadSfOptions(){
  const db = (document.getElementById("sfDatabase").value || "").trim();
  const sc = (document.getElementById("sfSchema").value || "").trim();
  const params = new URLSearchParams();
  if(db) params.set("database", db);
  if(sc) params.set("schema", sc);

  try{
    const resp = await fetch(getApiBase()+"/api/snowflake/options?"+params.toString());
    const data = await resp.json();
    if(data.defaults){
      if(!document.getElementById("sfWarehouse").value) document.getElementById("sfWarehouse").value = data.defaults.warehouse || "";
      if(!document.getElementById("sfDatabase").value)  document.getElementById("sfDatabase").value  = data.defaults.database || "";
      if(!document.getElementById("sfSchema").value)    document.getElementById("sfSchema").value    = data.defaults.schema || "";
      if(!document.getElementById("sfTable").value)     document.getElementById("sfTable").value     = data.defaults.table || "";
    }
    if(data.success){
      fillDatalist("sfWarehouseList", data.warehouses);
      fillDatalist("sfDatabaseList",  data.databases);
      fillDatalist("sfSchemaList",    data.schemas);
      fillDatalist("sfTableList",     data.tables);
      showToast("Snowflake warehouses & tables loaded.");
    } else {
      showToast(data.error || "Enter Snowflake details manually.");
    }
  }catch(e){
    showToast("Could not load Snowflake options.");
  }
}

async function pullFromSnowflake(){
  hideErr(); hideOk(); hideOverdue();
  const payload = {
    warehouse: (document.getElementById("sfWarehouse").value || "").trim(),
    database:  (document.getElementById("sfDatabase").value  || "").trim(),
    schema:    (document.getElementById("sfSchema").value    || "").trim(),
    table:     (document.getElementById("sfTable").value     || "").trim(),
    expected_columns: getExpectedCols(),
  };
  showToast("Connecting to Snowflake...");
  try{
    const resp = await fetch(getApiBase()+"/api/snowflake/pull", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if(!data.success){
      showErr("Snowflake Pull", data.error || "Failed to fetch data from Snowflake.");
      return;
    }
    allData = data.rows;
    filteredData = [...allData];
    showOk(`Pulled ${data.count} records from Snowflake.`);
    showOverdue(data.overdue || []);
    render();
  }catch(e){
    showErr("Snowflake Pull Error", e.message);
  }
}

const COL_MAP = {
  "EMP ID":["emp id","employee id","empid","emp_id","emp. id","empno","emp no"],
  "EMP NAME":["emp name","employee name","empname","name","emp_name","emp. name","employee"],
  "SKILL ASSIGNED":["skill assigned","skill","skill_assigned","skills assigned","skill name","assigned skill"],
  "PROFICIENCY":["proficiency","proficiency level","level","prof","profiency"],
  "TARGET DATE":["target date","target_date","targetdate","target completion date","target dt"],
  "CURRENT STATUS":["current status","status","current_status","currentstatus"],
  "LEARNING START DATE":["learning start date","start date","learning_start_date","startdate","learning start dt"],
  "E-LEARNING COMPLETION %":["e-learning completion %","elearning completion %","e learning completion %","elearning %","e-learning %","elearning completion","e-learning completion","elearning completion percentage","e-learning completion percentage","e learning completion percentage","elearningcompletionpercentage","elearning%","e-learning%","elearning completion%","e learning %","online learning completion %","online learning %"],
  "VILT COMPLETION %":["vilt completion %","vilt %","vilt completion","vilt completion percentage","viltcompletionpercentage","vilt completion%","vilt%","vilt complete %","vilt complete percentage"],
  "LEARNING COMPLETION DATE":["learning completion date","completion date","learning_completion_date"],
  "BEST SCORE":["best score","score","best_score","bestscore","best score %","top score"],
  "CERTIFIED DATE":["certified date","certification date","certified_date","cert date","certifieddate"],
  "EXEMPTED STATUS":["exempted status","exempted","exempt status","exempt","exemption status","is exempted"],
};
const REQUIRED = Object.keys(COL_MAP);
const STORAGE_COL_KEY = "lpt_expected_columns";
let editingCols = [];

function getExpectedCols(){
  try{
    const saved = localStorage.getItem(STORAGE_COL_KEY);
    if(saved){
      const parsed = JSON.parse(saved);
      if(Array.isArray(parsed) && parsed.length) return parsed;
    }
  }catch(e){}
  return [...REQUIRED];
}

function initColEditor(){
  editingCols = getExpectedCols();
  renderColList();
  renderColHintTags(editingCols);
}

function renderColList(){
  const list = document.getElementById("colList");
  if(!list) return;
  list.innerHTML = editingCols.map((col, idx) => `
    <div class="col-list-item">
      <input type="text" value="${esc(col)}" onchange="updateExpectedCol(${idx}, this.value)" oninput="editingCols[${idx}]=this.value"/>
      <button class="btn btn-danger btn-sm" onclick="removeExpectedCol(${idx})" title="Remove column">Remove</button>
    </div>
  `).join("");
}

function addExpectedCol(){
  const inp = document.getElementById("newColInput");
  const val = (inp.value || "").trim();
  if(!val){ showToast("Enter a column name first."); return; }
  if(editingCols.some(c => c.toLowerCase() === val.toLowerCase())){
    showToast("Column already exists.");
    return;
  }
  editingCols.push(val);
  inp.value = "";
  renderColList();
}

function updateExpectedCol(idx, val){
  editingCols[idx] = val.trim();
}

function removeExpectedCol(idx){
  if(editingCols.length <= 1){
    showToast("At least one column is required.");
    return;
  }
  editingCols.splice(idx, 1);
  renderColList();
}

function renderColHintTags(cols){
  const container = document.getElementById("colHintTags");
  if(!container) return;
  container.innerHTML = cols.map(label => `<span class="tag">${esc(label)}</span>`).join(" ");
}

function toggleColEditor(){
  const el = document.getElementById("colEditor");
  if(el.style.display === "none"){
    editingCols = getExpectedCols();
    renderColList();
    el.style.display = "block";
  } else {
    el.style.display = "none";
  }
}

function saveExpectedCols(){
  const cleaned = editingCols.map(c => c.trim()).filter(Boolean);
  if(!cleaned.length){ showToast("At least one column is required."); return; }
  editingCols = cleaned;
  localStorage.setItem(STORAGE_COL_KEY, JSON.stringify(cleaned));
  renderColHintTags(cleaned);
  document.getElementById("colEditor").style.display = "none";
  showToast("Expected columns saved (" + cleaned.length + "). Drop your CSV to test.");
}

function resetExpectedCols(){
  localStorage.removeItem(STORAGE_COL_KEY);
  initColEditor();
  showToast("Columns reset to defaults.");
}

const STAGES = [
  {label:"Completed",     color:"#198754", test:r=>r["CURRENT STATUS"]==="Completed"},
  {label:"In Progress",   color:"#fd7e14", test:r=>r["CURRENT STATUS"]==="In Progress"},
  {label:"Not Started",   color:"#dc3545", test:r=>r["CURRENT STATUS"]==="Not Started"},
  {label:"Exempted",      color:"#6f42c1", test:r=>r["CURRENT STATUS"]==="Exempted"},
];
const PROF_COLORS={"Advanced":"#0d6efd","Intermediate":"#0dcaf0","Beginner":"#6c757d"};

let allData=[];
let filteredData=[];

async function go(file){
  hideErr();hideOk();hideOverdue();
  if(!file.name.match(/\.csv$/i)){showErr("Wrong file type","Please upload a .csv file.");return;}

  if(apiConnected){
    const apiResult = await sendToApi(file);
    if(apiResult && apiResult.rows){
      allData      = apiResult.rows;
      filteredData = [...allData];
      render();
      return;
    }
    showToast("Falling back to local parsing...");
  }

  const r=new FileReader();
  r.onerror=()=>showErr("Read error","Could not read the file.");
  r.onload=e=>{
    try{
      const res=parseCSV(e.target.result);
      if(res.error){showErr("CSV Error",res.error);return;}
      allData=res.data;filteredData=[...allData];
      showOk("Loaded "+allData.length+" records locally.");
      render();
    }catch(ex){showErr("Error",ex.message);}
  };
  r.readAsText(file,"UTF-8");
}

function parseCSV(raw){
  raw=raw.replace(/^\uFEFF/,"").replace(/\r\n/g,"\n").replace(/\r/g,"\n");
  const lines=raw.split("\n").map(l=>l.trim()).filter(Boolean);
  if(lines.length<2)return{error:"File is empty or has only a header row."};
  const headers=splitLine(lines[0]).map(h=>h.trim());
  function norm(s){return s.toLowerCase().replace(/[\s\-_./% ]/g,"");}
  const activeCols=getExpectedCols();
  const idx={};
  const targetKeyMap={};
  activeCols.forEach(col=>{
    const upper=col.toUpperCase();
    const variants=COL_MAP[upper]?[col.toLowerCase(),...COL_MAP[upper]]:[col.toLowerCase()];
    let found=headers.findIndex(h=>variants.includes(h.toLowerCase().trim()));
    if(found===-1)found=headers.findIndex(h=>variants.some(v=>norm(v)===norm(h)));
    if(found===-1)found=headers.findIndex(h=>variants.some(v=>norm(h).includes(norm(v))||norm(v).includes(norm(h))));
    idx[col]=found;
    targetKeyMap[col]=COL_MAP[upper]?upper:col;
  });
  const missing=activeCols.filter(k=>idx[k]===-1);
  if(missing.length)return{error:"Missing column(s):\n"+missing.map(m=>"  • "+m).join("\n")+"\n\nFound:\n"+headers.map(h=>"  • "+h).join("\n")};
  const data=[];
  for(let i=1;i<lines.length;i++){
    const v=splitLine(lines[i]);
    const row={};
    REQUIRED.forEach(k=>{row[k]="";});
    activeCols.forEach(col=>{row[targetKeyMap[col]]=idx[col]===-1?"":(v[idx[col]]||"").trim();});
    if(!row["EMP ID"]&&!row["EMP NAME"]&&Object.values(row).every(x=>!x))continue;
    row["E-LEARNING COMPLETION %"]=clampPct(row["E-LEARNING COMPLETION %"]);
    row["VILT COMPLETION %"]=clampPct(row["VILT COMPLETION %"]);
    row["BEST SCORE"]=parseFloat((row["BEST SCORE"]||"0").replace(/[^0-9.]/g,""))||0;
    const el=row["E-LEARNING COMPLETION %"],vilt=row["VILT COMPLETION %"],sc=row["BEST SCORE"];
    const exSt=(row["EXEMPTED STATUS"]||"").toLowerCase();
    const rawSt=(row["CURRENT STATUS"]||"").toLowerCase();
    if(exSt.includes("yes")||exSt.includes("exempt"))row["CURRENT STATUS"]="Exempted";
    else if(sc>50 || (el>=100 && vilt>=100) || rawSt==="completed")row["CURRENT STATUS"]="Completed";
    else if(el===0&&vilt===0&&sc===0)row["CURRENT STATUS"]="Not Started";
    else row["CURRENT STATUS"]="In Progress";
    const p=row["PROFICIENCY"].toLowerCase();
    if(p.includes("adv"))row["PROFICIENCY"]="Advanced";
    else if(p.includes("int"))row["PROFICIENCY"]="Intermediate";
    else if(p.includes("beg")||p.includes("nov"))row["PROFICIENCY"]="Beginner";
    data.push(row);
  }
  if(!data.length)return{error:"No valid data rows found."};
  return{data};
}

function clampPct(v){const n=parseFloat((v||"0").replace(/[^0-9.]/g,""))||0;return Math.min(100,Math.max(0,n));}
function splitLine(line){const r=[];let cur="";let inQ=false;for(let i=0;i<line.length;i++){const c=line[i];if(c==='"'){if(inQ&&line[i+1]==='"'){cur+='"';i++;}else inQ=!inQ;}else if(c===','&&!inQ){r.push(cur.trim());cur="";}else cur+=c;}r.push(cur.trim());return r;}

function getRecordDate(r){
  return r["CERTIFIED DATE"] || r["LEARNING COMPLETION DATE"] || r["LEARNING START DATE"] || r["TARGET DATE"] || "";
}

function applyFilters(){
  const st=document.getElementById("fStatus").value;
  const pr=document.getElementById("fProf").value;
  const fromD=document.getElementById("fFrom").value;
  const toD=document.getElementById("fTo").value;
  const q=document.getElementById("fSearch").value.toLowerCase().trim();
  filteredData=allData.filter(r=>{
    if(st&&r["CURRENT STATUS"]!==st)return false;
    if(pr&&r["PROFICIENCY"]!==pr)return false;
    if(fromD||toD){
      const d=getRecordDate(r);
      if(!d)return false;
      if(fromD && d<fromD)return false;
      if(toD && d>toD)return false;
    }
    if(q){const hay=(r["EMP ID"]+r["EMP NAME"]+r["SKILL ASSIGNED"]).toLowerCase();if(!hay.includes(q))return false;}
    return true;
  });
  render();
}

function resetFilters(){
  document.getElementById("fStatus").value="";
  document.getElementById("fProf").value="";
  document.getElementById("fFrom").value="";
  document.getElementById("fTo").value="";
  document.getElementById("fSearch").value="";
  filteredData=[...allData];render();
}

function render(){
  const rows=filteredData;
  document.getElementById("filterBar").style.display="flex";
  const total=rows.length,cert=rows.filter(r=>r["CURRENT STATUS"]==="Completed").length,inp=rows.filter(r=>r["CURRENT STATUS"]==="In Progress").length,ns=rows.filter(r=>r["CURRENT STATUS"]==="Not Started").length,ex=rows.filter(r=>r["CURRENT STATUS"]==="Exempted").length;
  const scs=rows.filter(r=>r["BEST SCORE"]>0).map(r=>r["BEST SCORE"]);
  const avg=scs.length?(scs.reduce((a,b)=>a+b,0)/scs.length).toFixed(1):"—";
  const sg=document.getElementById("sg");
  sg.style.display="grid";
  sg.innerHTML=`
    <div class="summary-card tot"><div class="value">${total}</div><div class="label">Total</div></div>
    <div class="summary-card cert"><div class="value">${cert}</div><div class="label">Completed</div></div>
    <div class="summary-card inp"><div class="value">${inp}</div><div class="label">In Progress</div></div>
    <div class="summary-card ns"><div class="value">${ns}</div><div class="label">Not Started</div></div>
    <div class="summary-card ex"><div class="value">${ex}</div><div class="label">Exempted</div></div>
    <div class="summary-card avg"><div class="value">${avg}</div><div class="label">Avg Score</div></div>`;
  document.getElementById("chartSection").style.display="grid";
  const statusData=[{label:"Completed",value:cert,color:"#198754"},{label:"In Progress",value:inp,color:"#fd7e14"},{label:"Not Started",value:ns,color:"#dc3545"},{label:"Exempted",value:ex,color:"#6f42c1"}].filter(d=>d.value>0);
  drawDonut("donut1","legend1","d1num","d1lbl",statusData,total,"Total","status");
  const profCounts={};rows.forEach(r=>{const p=r["PROFICIENCY"]||"Unknown";profCounts[p]=(profCounts[p]||0)+1;});
  const profData=Object.entries(profCounts).map(([label,value])=>({label,value,color:PROF_COLORS[label]||"#6c757d"}));
  drawDonut("donut2","legend2","d2num","d2lbl",profData,total,"Total","proficiency");
  const extraCols = getExtraCols(rows);
  const extraHdrs = extraCols.map(c => `<th>${esc(c)}</th>`).join("");
  const rb=document.getElementById("rptBody");rb.innerHTML="";
  STAGES.forEach(stage=>{
    const sr=rows.filter(r=>stage.test(r));if(!sr.length)return;
    const g=document.createElement("div");g.className="sg-group";
    g.innerHTML=`<div class="sg-label"><span>${stage.label}</span> <span style="font-size:12px; font-weight:normal; color:#666;">(${sr.length} employees)</span></div><div class="table-responsive"><table><thead><tr><th>#</th><th>EMP ID</th><th>Name</th><th>Skill</th><th>Proficiency</th><th>Start Date</th><th>Target Date</th><th>eLearning %</th><th>VILT %</th><th>Completion Date</th><th>Best Score</th><th>Certified Date</th><th>Status</th><th>Exempted</th>${extraHdrs}</tr></thead><tbody>${sr.map((r,i)=>buildRow(r,i+1,stage.color,extraCols)).join("")}</tbody></table></div>`;
    rb.appendChild(g);
  });
  document.getElementById("rptSec").style.display="block";
}

function getExtraCols(rows){
  if(!rows || !rows.length) return [];
  const std = new Set(REQUIRED);
  const extras = [];
  Object.keys(rows[0]).forEach(k => {
    if(!std.has(k)) extras.push(k);
  });
  return extras;
}

function drawDonut(svgId,legendId,numId,lblId,data,total,defaultLbl,type){
  const svg=document.getElementById(svgId);const cx=90,cy=90,r=75,ir=48;let html="";let startAngle=-Math.PI/2;const paths=[];
  data.forEach((d,i)=>{const angle=(d.value/total)*Math.PI*2;const endAngle=startAngle+angle;const x1=cx+r*Math.cos(startAngle),y1=cy+r*Math.sin(startAngle),x2=cx+r*Math.cos(endAngle),y2=cy+r*Math.sin(endAngle),x3=cx+ir*Math.cos(endAngle),y3=cy+ir*Math.sin(endAngle),x4=cx+ir*Math.cos(startAngle),y4=cy+ir*Math.sin(startAngle);const large=angle>Math.PI?1:0;const path=`M${x1},${y1} A${r},${r},0,${large},1,${x2},${y2} L${x3},${y3} A${ir},${ir},0,${large},0,${x4},${y4} Z`;const pct=total>0?((d.value/total)*100).toFixed(1):0;paths.push({path,color:d.color,label:d.label,value:d.value,pct,i});startAngle=endAngle;});
  html=paths.map(p=>`<path d="${p.path}" fill="${p.color}" opacity="0.9" style="cursor:pointer;transition:opacity .15s;" onmouseenter="this.style.opacity='1';document.getElementById('${numId}').textContent='${p.value}';document.getElementById('${lblId}').textContent='${p.label}'" onmouseleave="this.style.opacity='.9';document.getElementById('${numId}').textContent='${total}';document.getElementById('${lblId}').textContent='${defaultLbl}'" onclick="showDrill('${p.label}','${type}','${p.color}')"/>`).join("");
  html+=`<circle cx="${cx}" cy="${cy}" r="${ir-2}" fill="#ffffff"/>`;
  svg.innerHTML=html;
  document.getElementById(numId).textContent=total;document.getElementById(lblId).textContent=defaultLbl;
  const leg=document.getElementById(legendId);
  leg.innerHTML=paths.map(p=>`<div class="legend-item" id="li-${type}-${p.i}" onclick="showDrill('${p.label}','${type}','${p.color}')" onmouseenter="highlightSegment('${svgId}',${p.i},true,'${numId}','${lblId}','${p.value}','${p.label}')" onmouseleave="highlightSegment('${svgId}',${p.i},false,'${numId}','${lblId}','${total}','${defaultLbl}')"><span class="legend-dot" style="background:${p.color}"></span><span class="legend-label">${p.label}</span><span class="legend-val">${p.value}</span><span class="legend-pct">(${p.pct}%)</span></div>`).join("");
}

function highlightSegment(svgId,idx,on,numId,lblId,val,label){const paths=document.getElementById(svgId).querySelectorAll("path");if(paths[idx]){paths[idx].style.opacity=on?"1":".9";}document.getElementById(numId).textContent=val;document.getElementById(lblId).textContent=label;}

function showDrill(label,type,color){
  let group=[];
  if(type==="status"){group=filteredData.filter(r=>r["CURRENT STATUS"]===label);}
  else if(type==="proficiency"){group=filteredData.filter(r=>r["PROFICIENCY"]===label);}
  document.getElementById("drillTitle").textContent=label+" - Employee Details";
  document.getElementById("drillCount").textContent=group.length+" record(s)";
  const tbody=document.getElementById("drillBody");
  tbody.innerHTML=group.map((r,i)=>{
    const sc=r["BEST SCORE"]>0?r["BEST SCORE"]:"—";
    let pill="";if(r["CURRENT STATUS"]==="Completed")pill=`<span class="status-pill sp-done">Completed</span>`;else if(r["CURRENT STATUS"]==="In Progress")pill=`<span class="status-pill sp-prog">In Progress</span>`;else if(r["CURRENT STATUS"]==="Exempted")pill=`<span class="status-pill sp-ex">Exempted</span>`;else pill=`<span class="status-pill sp-ns">Not Started</span>`;
    const ep=r["E-LEARNING COMPLETION %"],vp=r["VILT COMPLETION %"];
    return `<tr><td>${i+1}</td><td>${esc(r["EMP ID"])}</td><td><strong>${esc(r["EMP NAME"])}</strong></td><td>${esc(r["SKILL ASSIGNED"])||"—"}</td><td>${profBadge(r["PROFICIENCY"])}</td><td>${pill}</td><td><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${ep}%"></div></div> ${ep}%</td><td><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${vp}%; background:#6f42c1;"></div></div> ${vp}%</td><td>${sc}</td><td>${esc(r["CERTIFIED DATE"])||"—"}</td></tr>`;
  }).join("");
  const panel=document.getElementById("drillPanel");panel.style.display="block";panel.scrollIntoView({behavior:"smooth",block:"start"});
}

function closeDrill(){document.getElementById("drillPanel").style.display="none";}

function profBadge(p){if(p==="Advanced")return`<span class="prof-badge prof-b">${p}</span>`;if(p==="Intermediate")return`<span class="prof-badge prof-i">${p}</span>`;if(p==="Beginner")return`<span class="prof-badge prof-n">${p}</span>`;return`<span style="color:#666;font-size:12px;">${esc(p)||"—"}</span>`;}

function buildRow(r,i,color,extraCols){
  const ep=r["E-LEARNING COMPLETION %"],vp=r["VILT COMPLETION %"],sc=r["BEST SCORE"];
  let pill="";if(r["CURRENT STATUS"]==="Completed")pill=`<span class="status-pill sp-done">Completed</span>`;else if(r["CURRENT STATUS"]==="In Progress")pill=`<span class="status-pill sp-prog">In Progress</span>`;else if(r["CURRENT STATUS"]==="Exempted")pill=`<span class="status-pill sp-ex">Exempted</span>`;else pill=`<span class="status-pill sp-ns">Not Started</span>`;
  const extraTds = (extraCols || []).map(c => `<td>${esc(r[c]) || "—"}</td>`).join("");
  return `<tr><td>${i}</td><td>${esc(r["EMP ID"])}</td><td><strong>${esc(r["EMP NAME"])}</strong></td><td>${esc(r["SKILL ASSIGNED"])||"—"}</td><td>${profBadge(r["PROFICIENCY"])}</td><td>${esc(r["LEARNING START DATE"])||"—"}</td><td>${esc(r["TARGET DATE"])||"—"}</td><td><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${ep}%"></div></div> ${ep}%</td><td><div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${vp}%; background:#6f42c1;"></div></div> ${vp}%</td><td>${esc(r["LEARNING COMPLETION DATE"])||"—"}</td><td>${sc>0?sc:"—"}</td><td>${esc(r["CERTIFIED DATE"])||"—"}</td><td>${pill}</td><td>${esc(r["EXEMPTED STATUS"])||"—"}</td>${extraTds}</tr>`;
}

function esc(s){return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function getReportData(){
  const STATUSES=["Completed","In Progress","Not Started","Exempted"];
  const COLS=["EMP ID","EMP NAME","SKILL ASSIGNED","PROFICIENCY","TARGET DATE","CURRENT STATUS","LEARNING START DATE","E-LEARNING COMPLETION %","VILT COMPLETION %","LEARNING COMPLETION DATE","BEST SCORE","CERTIFIED DATE","EXEMPTED STATUS"];
  const total=filteredData.length,cert=filteredData.filter(r=>r["CURRENT STATUS"]==="Completed").length,inp=filteredData.filter(r=>r["CURRENT STATUS"]==="In Progress").length,ns=filteredData.filter(r=>r["CURRENT STATUS"]==="Not Started").length,ex=filteredData.filter(r=>r["CURRENT STATUS"]==="Exempted").length;
  const scs=filteredData.filter(r=>r["BEST SCORE"]>0).map(r=>r["BEST SCORE"]);
  const avg=scs.length?(scs.reduce((a,b)=>a+b,0)/scs.length).toFixed(1):0;
  const rate=total?((cert/total)*100).toFixed(1):0;
  const date=new Date().toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric"});
  return{COLS,STATUSES,total,cert,inp,ns,ex,avg,rate,date};
}

async function exportExcel(){
  if(!filteredData.length){showToast("No data loaded yet.");return;}

  if(apiConnected){
    try{
      showToast("Generating colorful Excel report with charts...");
      const resp = await fetch(getApiBase()+"/api/export/excel", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({rows: filteredData}),
      });
      if(resp.ok){
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "Learning_Progress_Report_"+new Date().toISOString().slice(0,10)+".xlsx";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast("Styled Excel report downloaded.");
        return;
      }
    }catch(e){}
  }

  if(typeof XLSX==="undefined"){showToast("Excel library not loaded.");exportReportCSV();return;}
  try{
    const{COLS,STATUSES,total,cert,inp,ns,ex,avg,rate,date}=getReportData();
    const wb=XLSX.utils.book_new();
    const summaryRows=[["LEARNING PROGRESS REPORT"],["Generated:",date],[""],["METRIC","VALUE"],["Total Employees",total],["Certified / Completed",cert],["In Progress",inp],["Not Started",ns],["Exempted",ex],["Avg Best Score",avg],["Completion Rate (%)",rate]];
    const wsSummary=XLSX.utils.aoa_to_sheet(summaryRows);wsSummary["!cols"]=[{wch:28},{wch:16}];wsSummary["!merges"]=[{s:{r:0,c:0},e:{r:0,c:1}}];XLSX.utils.book_append_sheet(wb,wsSummary,"Summary");
    const reportRows=[["LEARNING PROGRESS REPORT - "+date],[]];
    STATUSES.forEach(status=>{const group=filteredData.filter(r=>r["CURRENT STATUS"]===status);if(!group.length)return;reportRows.push([status.toUpperCase()+" ("+group.length+" employees)"]);reportRows.push(COLS);group.forEach(r=>reportRows.push(COLS.map(c=>{const v=r[c];if(c==="E-LEARNING COMPLETION %"||c==="VILT COMPLETION %")return v+"%";return v||"";})));reportRows.push([]);reportRows.push([]);});
    const wsReport=XLSX.utils.aoa_to_sheet(reportRows);wsReport["!cols"]=[10,18,22,14,13,14,16,18,16,20,11,14,14].map(w=>({wch:w}));XLSX.utils.book_append_sheet(wb,wsReport,"Progress Report");
    STATUSES.forEach(status=>{const group=filteredData.filter(r=>r["CURRENT STATUS"]===status);if(!group.length)return;const rows=[COLS];group.forEach(r=>rows.push(COLS.map(c=>r[c]||"")));const ws=XLSX.utils.aoa_to_sheet(rows);ws["!cols"]=[10,18,22,14,13,14,16,18,16,20,11,14,14].map(w=>({wch:w}));XLSX.utils.book_append_sheet(wb,ws,status.substring(0,31));});
    XLSX.writeFile(wb,"Learning_Progress_Report_"+new Date().toISOString().slice(0,10)+".xlsx");
    showToast("Excel report downloaded.");
  }catch(e){exportReportCSV();}
}

function exportReportCSV(){
  if(!filteredData.length){showToast("No data loaded.");return;}
  const{COLS,STATUSES,total,cert,inp,ns,ex,avg,rate,date}=getReportData();
  const esc2=v=>{const s=String(v==null?"":v);return(s.includes(",")||s.includes('"')||s.includes("\n"))?'"'+s.replace(/"/g,'""')+'"':s;};
  let csv="LEARNING PROGRESS REPORT\nGenerated:,"+date+"\n\nSUMMARY\n";csv+=`Total Employees,${total}\nCertified,${cert}\nIn Progress,${inp}\nNot Started,${ns}\nExempted,${ex}\nAvg Score,${avg}\nCompletion Rate (%),${rate}\n\n`;
  STATUSES.forEach(status=>{const group=filteredData.filter(r=>r["CURRENT STATUS"]===status);if(!group.length)return;csv+=status.toUpperCase()+" ("+group.length+" employees)\n";csv+=COLS.map(esc2).join(",")+"\n";group.forEach(r=>{csv+=COLS.map(c=>esc2(r[c]||"")).join(",")+"\n";});csv+="\n";});
  const blob=new Blob(["\uFEFF"+csv],{type:"text/csv;charset=utf-8;"});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download="Learning_Progress_Report_"+new Date().toISOString().slice(0,10)+".csv";document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);
  showToast("CSV report downloaded.");
}

const TEMPLATE=[
  ["EMP ID","EMP NAME","SKILL ASSIGNED","PROFICIENCY","TARGET DATE","CURRENT STATUS","LEARNING START DATE","E-LEARNING COMPLETION %","VILT COMPLETION %","LEARNING COMPLETION DATE","BEST SCORE","CERTIFIED DATE","EXEMPTED STATUS"],
  ["EMP001","Anitha Sharma","AWS Cloud Practitioner","Advanced","2026-06-25","Completed","2026-05-10",100,100,"2026-06-18",92,"2026-06-20","No"],
  ["EMP002","Ravi Kumar","Oracle SQL Database","Intermediate","2026-07-15","Completed","2026-06-01",100,100,"2026-07-10",86,"2026-07-12","No"],
  ["EMP003","Meena Patel","Azure Fundamentals","Intermediate","2026-07-25","Completed","2026-06-15",100,100,"2026-07-20",89,"2026-07-22","No"],
  ["EMP004","John Doe","Python Programming","Beginner","2026-08-20","Completed","2026-07-05",100,100,"2026-08-14",84,"2026-08-16","No"],
  ["EMP005","Priya Sundaram","AWS Solutions Architect","Advanced","2026-08-30","Completed","2026-07-12",100,100,"2026-08-25",94,"2026-08-27","No"],
  ["EMP006","Suresh Reddy","Microsoft Azure Admin","Intermediate","2026-09-20","Completed","2026-08-01",100,100,"2026-09-15",88,"2026-09-18","No"],
  ["EMP007","Kavitha Nair","Google Cloud Associate","Beginner","2026-09-28","Completed","2026-08-10",100,100,"2026-09-24",81,"2026-09-26","No"],
  ["EMP008","Arjun Verma","Oracle Database Admin","Advanced","2026-10-15","Completed","2026-09-01",100,100,"2026-10-10",91,"2026-10-12","No"],
  ["EMP009","Divya Krishnan","AWS Certified Developer","Advanced","2026-10-25","Completed","2026-09-05",100,100,"2026-10-20",95,"2026-10-22","No"],
  ["EMP010","Ramesh Gupta","Cisco CCNA Networking","Beginner","2026-11-18","Completed","2026-10-01",100,100,"2026-11-12",83,"2026-11-15","No"],
  ["EMP011","Lakshmi Iyer","Salesforce Administrator","Intermediate","2026-11-22","Completed","2026-10-05",100,100,"2026-11-18",90,"2026-11-20","No"],
  ["EMP012","Vikram Singh","Python Data Science","Intermediate","2026-11-20","In Progress","2026-10-10",45,30,"",0,"","No"],
  ["EMP013","Nisha Agarwal","SAP Basics","Beginner","2026-10-01","Exempted","","","","","","","Yes - Already Certified"],
  ["EMP014","Karan Mehta","Docker & Kubernetes","Advanced","2026-11-10","In Progress","2026-09-15",35,20,"",0,"","No"],
  ["EMP015","Sneha Roy","React Frontend Dev","Intermediate","2026-12-05","In Progress","2026-10-20",75,65,"",0,"","No"],
  ["EMP016","Deepak Joshi","AWS Cloud Practitioner","Beginner","2026-11-15","Not Started","",0,0,"",0,"","No"],
  ["EMP017","Pooja Menon","Python Data Science","Intermediate","2026-12-12","In Progress","2026-10-25",80,75,"",0,"","No"],
  ["EMP018","Nikhil Sharma","Docker & Kubernetes","Intermediate","2026-12-20","In Progress","2026-11-01",60,55,"",0,"","No"],
  ["EMP019","Aarti Desai","Azure Fundamentals","Beginner","2026-11-28","Not Started","",0,0,"",0,"","No"],
  ["EMP020","Sanjay Kulkarni","React Frontend Dev","Advanced","2026-12-18","In Progress","2026-11-02",85,80,"",0,"","No"],
  ["EMP021","Tanvi Kapoor","AWS Solutions Architect","Advanced","2026-11-29","In Progress","2026-10-15",40,35,"",0,"","No"],
  ["EMP022","Manish Tiwari","Oracle SQL Database","Beginner","2026-12-30","Not Started","",0,0,"",0,"","No"],
  ["EMP023","Swati Bansal","Google Cloud Associate","Intermediate","2026-12-22","In Progress","2026-11-05",70,60,"",0,"","No"],
  ["EMP024","Rahul Verma","Cisco CCNA Networking","Beginner","2026-11-12","Not Started","",0,0,"",0,"","No"],
];
function dlTemplate(){const csv=TEMPLATE.map(r=>r.join(",")).join("\n");const a=document.createElement("a");a.href="data:text/csv;charset=utf-8,"+encodeURIComponent(csv);a.download="learning_tracker_template.csv";a.click();showToast("Template downloaded.");}
function loadSample(){
  const[hdr,...rows]=TEMPLATE;
  allData=rows.map(r=>{const obj={};hdr.forEach((h,i)=>obj[h]=String(r[i]||""));obj["E-LEARNING COMPLETION %"]=clampPct(obj["E-LEARNING COMPLETION %"]);obj["VILT COMPLETION %"]=clampPct(obj["VILT COMPLETION %"]);obj["BEST SCORE"]=parseFloat(obj["BEST SCORE"])||0;const el2=obj["E-LEARNING COMPLETION %"],vilt2=obj["VILT COMPLETION %"],sc2=obj["BEST SCORE"],exSt2=(obj["EXEMPTED STATUS"]||"").toLowerCase();if(exSt2.includes("yes")||exSt2.includes("exempt"))obj["CURRENT STATUS"]="Exempted";else if(sc2>50||(el2>=100&&vilt2>=100))obj["CURRENT STATUS"]="Completed";else if(el2===0&&vilt2===0&&sc2===0)obj["CURRENT STATUS"]="Not Started";else obj["CURRENT STATUS"]="In Progress";const p=obj["PROFICIENCY"].toLowerCase();if(p.includes("adv"))obj["PROFICIENCY"]="Advanced";else if(p.includes("int"))obj["PROFICIENCY"]="Intermediate";else if(p.includes("beg")||p.includes("nov"))obj["PROFICIENCY"]="Beginner";return obj;});
  filteredData=[...allData];hideErr();hideOverdue();showOk("Sample data loaded ("+allData.length+" records).");render();
}

function showOverdue(list){
  const bar=document.getElementById("overdueBar");
  if(!list||!list.length){bar.style.display="none";return;}
  const overdueCnt=list.filter(x=>x.severity==="overdue").length;
  const dueSoonCnt=list.length-overdueCnt;
  document.getElementById("overdueMsg").textContent=`${overdueCnt} overdue, ${dueSoonCnt} due within 7 days (e.g. ${list[0].emp_name} — ${list[0].skill}, target ${list[0].target_date}).`;
  bar.style.display="block";
}
function hideOverdue(){document.getElementById("overdueBar").style.display="none";}

function showErr(t,m){document.getElementById("errTitle").textContent=t;document.getElementById("errMsg").textContent=m;document.getElementById("errBox").style.display="block";document.getElementById("sg").style.display="none";document.getElementById("rptSec").style.display="none";document.getElementById("filterBar").style.display="none";document.getElementById("chartSection").style.display="none";document.getElementById("drillPanel").style.display="none";}
function hideErr(){document.getElementById("errBox").style.display="none";}
function showOk(m){document.getElementById("okMsg").textContent=m;document.getElementById("okBar").style.display="block";}
function hideOk(){document.getElementById("okBar").style.display="none";}
let tt;
function showToast(m){const el=document.getElementById("toast");el.textContent=m;el.classList.add("show");clearTimeout(tt);tt=setTimeout(()=>el.classList.remove("show"),3000);}

// =========================================================================
// Tabs, Secondary DB Link, ML Analysis & Customizable Dashboard
// =========================================================================
let lastAnalysis = null;
let growthChartInst = null;
let gapChartInst = null;
const DASH_PREF_KEY = "lpt_dash_prefs";

function switchTab(tab){
  const isOver = tab === "overview";
  document.getElementById("viewOverview").style.display = isOver ? "block" : "none";
  document.getElementById("viewAnalysis").style.display = isOver ? "none" : "block";
  document.getElementById("tabBtnOverview").classList.toggle("active", isOver);
  document.getElementById("tabBtnAnalysis").classList.toggle("active", !isOver);
  if(!isOver){
    loadDashPrefs();
    if(filteredData.length && !lastAnalysis && apiConnected){
      runMlAnalysis();
    }
  }
}

function togglePanel(id){
  const el = document.getElementById(id);
  el.style.display = el.style.display === "none" ? "block" : "none";
}

function getDashPrefs(){
  try{
    const saved = localStorage.getItem(DASH_PREF_KEY);
    if(saved) return JSON.parse(saved);
  }catch(e){}
  return {showKpis:true, showGrowth:true, showGaps:true, showTrain:true, growthType:"line", gapType:"bar"};
}

function loadDashPrefs(){
  const p = getDashPrefs();
  document.getElementById("optShowKpis").checked = p.showKpis !== false;
  document.getElementById("optShowGrowth").checked = p.showGrowth !== false;
  document.getElementById("optShowGaps").checked = p.showGaps !== false;
  document.getElementById("optShowTrain").checked = p.showTrain !== false;
  document.getElementById("optGrowthType").value = p.growthType || "line";
  document.getElementById("optGapType").value = p.gapType || "bar";
}

function saveDashPrefs(){
  const p = {
    showKpis: document.getElementById("optShowKpis").checked,
    showGrowth: document.getElementById("optShowGrowth").checked,
    showGaps: document.getElementById("optShowGaps").checked,
    showTrain: document.getElementById("optShowTrain").checked,
    growthType: document.getElementById("optGrowthType").value,
    gapType: document.getElementById("optGapType").value,
  };
  localStorage.setItem(DASH_PREF_KEY, JSON.stringify(p));
  if(lastAnalysis) renderAnalysis(lastAnalysis);
}

function useSampleCompanyDb(){
  document.getElementById("secDbUrl").value = "sqlite:///company_hr.db";
  document.getElementById("secDbSchema").value = "";
  document.getElementById("secDbTable").value = "hr_employees";
  document.getElementById("secJoinLeft").value = "EMP ID";
  document.getElementById("secJoinRight").value = "employee_id";
  fetchSecondaryTables();
}

async function fetchSecondaryTables(){
  const dbUrl = (document.getElementById("secDbUrl").value || "").trim();
  const schema = (document.getElementById("secDbSchema").value || "").trim();
  if(!dbUrl){ showToast("Enter a Database URL first."); return; }
  try{
    const resp = await fetch(getApiBase()+"/api/connectors/tables", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({db_url: dbUrl, schema}),
    });
    const data = await resp.json();
    if(!data.success){ showToast(data.error || "Failed to list tables."); return; }
    fillDatalist("secDbTableList", data.tables);
    showToast(`Found ${data.tables.length} table(s).`);
  }catch(e){
    showToast("Connection error: " + e.message);
  }
}

async function loadSampleAndAnalyze(){
  loadSample();
  document.getElementById("secDbUrl").value = "sqlite:///company_hr.db";
  document.getElementById("secDbSchema").value = "";
  document.getElementById("secDbTable").value = "hr_employees";
  document.getElementById("secJoinLeft").value = "EMP ID";
  document.getElementById("secJoinRight").value = "employee_id";
  await runMlAnalysis();
}

function showMlErr(msg){
  const box = document.getElementById("mlErrBox");
  document.getElementById("mlErrMsg").textContent = msg;
  box.style.display = "block";
}
function hideMlErr(){
  document.getElementById("mlErrBox").style.display = "none";
}

async function runMlAnalysis(){
  hideMlErr();
  if(!filteredData.length){
    showMlErr("No data loaded yet. Click 'Load Sample Data & Analyze' or upload a CSV in Overview.");
    return;
  }
  const payload = {
    rows: filteredData,
    db_url: (document.getElementById("secDbUrl").value || "").trim(),
    schema: (document.getElementById("secDbSchema").value || "").trim(),
    table: (document.getElementById("secDbTable").value || "").trim(),
    left_key: (document.getElementById("secJoinLeft").value || "EMP ID").trim(),
    right_key: (document.getElementById("secJoinRight").value || "").trim(),
  };
  showToast("Running ML analysis...");
  try{
    const resp = await fetch(getApiBase()+"/api/analysis/run", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    if(resp.status === 405){
      showMlErr("Server returned 405 (Method Not Allowed). An older app.py is still running on port 5000 — stop it and restart: .\\.venv\\Scripts\\python.exe app.py");
      return;
    }
    const data = await resp.json();
    if(!data.success){
      showMlErr(data.error || "Analysis failed.");
      return;
    }
    apiConnected = true;
    lastAnalysis = data;
    renderAnalysis(data);
    showToast("ML analysis complete.");
  }catch(e){
    showMlErr("Could not reach Flask server at " + getApiBase() + ". Make sure you ran: .\\.venv\\Scripts\\python.exe app.py (" + e.message + ")");
  }
}

function renderAnalysis(data){
  const p = getDashPrefs();
  document.getElementById("mlModelBadge").textContent =
    `Models: ${data.models.risk_model} | ${data.models.growth_model}`;

  // KPIs
  const kpiEl = document.getElementById("mlKpis");
  if(p.showKpis){
    const k = data.kpis;
    kpiEl.style.display = "grid";
    kpiEl.innerHTML = `
      <div class="summary-card tot"><div class="value">${k.current_readiness_pct}%</div><div class="label">Current Readiness</div></div>
      <div class="summary-card cert"><div class="value">${k.projected_readiness_pct}%</div><div class="label">Projected (4 Mo)</div></div>
      <div class="summary-card inp"><div class="value">${k.needs_training_count}</div><div class="label">Need Training</div></div>
      <div class="summary-card ns"><div class="value">${k.high_risk_count}</div><div class="label">High Risk</div></div>
    `;
  } else {
    kpiEl.style.display = "none";
  }

  // Charts
  const chartsEl = document.getElementById("mlCharts");
  chartsEl.style.display = (p.showGrowth || p.showGaps) ? "grid" : "none";
  document.getElementById("cardGrowthChart").style.display = p.showGrowth ? "block" : "none";
  document.getElementById("cardGapChart").style.display = p.showGaps ? "block" : "none";

  if(p.showGrowth && typeof Chart !== "undefined"){
    if(growthChartInst) growthChartInst.destroy();
    const g = data.growth;
    growthChartInst = new Chart(document.getElementById("growthCanvas"), {
      type: p.growthType || "line",
      data: {
        labels: g.labels,
        datasets: [
          {label: "Actual Readiness %", data: g.actual, borderColor: "#0d6efd", backgroundColor: "rgba(13,110,253,0.15)", tension: 0.25},
          {label: "ML Forecast %", data: g.forecast, borderColor: "#198754", backgroundColor: "rgba(25,135,84,0.15)", borderDash: [6, 4], tension: 0.25},
        ],
      },
      options: {responsive: true, maintainAspectRatio: false, scales: {y: {min: 0, max: 100}}},
    });
  }

  if(p.showGaps && typeof Chart !== "undefined"){
    if(gapChartInst) gapChartInst.destroy();
    const gaps = (data.skill_gaps || []).slice(0, 10);
    const gapType = p.gapType || "bar";
    if(gapType === "doughnut"){
      gapChartInst = new Chart(document.getElementById("gapCanvas"), {
        type: "doughnut",
        data: {
          labels: gaps.map(x => x.skill),
          datasets: [{label: "Needs Training", data: gaps.map(x => x.needs_training), backgroundColor: ["#dc3545","#fd7e14","#ffc107","#0d6efd","#6f42c1","#20c997","#0dcaf0","#6c757d","#198754","#d63384"]}],
        },
        options: {responsive: true, maintainAspectRatio: false},
      });
    } else {
      gapChartInst = new Chart(document.getElementById("gapCanvas"), {
        type: "bar",
        data: {
          labels: gaps.map(x => x.skill),
          datasets: [
            {label: "Completed", data: gaps.map(x => x.completed), backgroundColor: "#198754"},
            {label: "Needs Training", data: gaps.map(x => x.needs_training), backgroundColor: "#dc3545"},
          ],
        },
        options: {responsive: true, maintainAspectRatio: false, scales: {x: {stacked: false}, y: {beginAtZero: true}}},
      });
    }
  }

  // Training Priority Table
  const trainCard = document.getElementById("cardTrainList");
  if(p.showTrain){
    trainCard.style.display = "block";
    const list = data.training_priority || [];
    document.getElementById("trainCount").textContent = `${list.length} employee(s) flagged`;
    document.getElementById("trainBody").innerHTML = list.map((r, i) => {
      const pCls = r.priority === "High" ? "prio-high" : r.priority === "Medium" ? "prio-med" : "prio-low";
      return `<tr>
        <td>${i + 1}</td>
        <td>${esc(r.emp_id)}</td>
        <td><strong>${esc(r.emp_name)}</strong></td>
        <td>${esc(r.skill)}</td>
        <td>${esc(r.status)}</td>
        <td>${r.elearning_pct}%</td>
        <td>${r.vilt_pct}%</td>
        <td><strong>${r.risk_score}%</strong></td>
        <td><span class="status-pill ${pCls}">${r.priority}</span></td>
        <td>${esc(r.reason)}</td>
      </tr>`;
    }).join("");
  } else {
    trainCard.style.display = "none";
  }
}
