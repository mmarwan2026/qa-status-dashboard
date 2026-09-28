import os, sys, json, html
from datetime import datetime
from collections import OrderedDict, Counter
from urllib.parse import quote
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

COLLECTION_URL = "http://azuredevops.ntgcloud.net/DefaultCollection"
PROJECT = "Red Sea -Whistleblowing Management System"
PROJECT_DISPLAY_NAME = "Red Sea - Whistleblowing Management System"
API_VERSION = "7.0"
PAT = os.getenv("AZURE_PAT")
OUTPUT_FILE = os.path.join(BASE_DIR, "QA_Status_Dashboard.html")

COLORS = {"New":"#6941C6","Open":"#D92D20","Active":"#1570EF","In Progress":"#1570EF","Ready":"#1570EF","Design":"#6941C6","Passed":"#039855","Done":"#039855","Closed":"#039855","Failed":"#D92D20","Fails":"#D92D20","Blocked":"#DC6803","Block":"#DC6803","Resolved":"#DC6803","Removed":"#98A2B3"}
ORDER = ["New","Open","Active","In Progress","Ready","Design","Passed","Done","Closed","Resolved","Blocked","Block","Failed","Fails","Removed"]
session=requests.Session()
if PAT: session.auth=("",PAT)
session.headers.update({"Accept":"application/json","Content-Type":"application/json"})


def validate_pat():
    value = (PAT or "").strip()
    placeholders = {
        "", "YOUR_PAT", "YOUR_REAL_PAT", "YOUR_REAL_PAT_HERE",
        "PASTE_PAT_HERE", "CHANGE_ME", "xxx", "xxxx"
    }
    if value.upper() in {x.upper() for x in placeholders}:
        print("")
        print("PAT Configuration: FAILED")
        print("Reason: AZURE_PAT is missing or still contains the default placeholder.")
        print("Open the .env file beside QA_Status_Dashboard.py and set:")
        print("AZURE_PAT=<your actual Azure DevOps PAT>")
        return False
    return True

def test_azure_auth():
    url = azure_url("_apis/projects")
    try:
        r = session.get(url, params={"api-version": API_VERSION}, timeout=20)
    except requests.RequestException as e:
        print("")
        print("Azure DevOps Connection: FAILED")
        print("Reason:", str(e))
        print("Check VPN/network access and COLLECTION_URL.")
        return False

    if r.status_code == 401:
        print("")
        print("Azure DevOps Authentication: FAILED (401 Unauthorized)")
        print("The server was reached, but the supplied PAT was not accepted.")
        print("Check that the PAT is correct, active/not expired, and authorized for this Azure DevOps Server.")
        return False
    if r.status_code == 403:
        print("")
        print("Azure DevOps Authorization: FAILED (403 Forbidden)")
        print("Authentication succeeded or was recognized, but access is not permitted.")
        print("Check PAT scopes and project/collection permissions.")
        return False
    if not r.ok:
        print("")
        print(f"Azure DevOps Connection: FAILED (HTTP {r.status_code})")
        print((r.text or "")[:500])
        return False

    try:
        count = len(r.json().get("value", []))
    except Exception:
        count = 0
    print(f"Azure DevOps Authentication: PASS ({count} project(s) visible)")
    return True

def azure_url(path): return COLLECTION_URL.rstrip("/")+"/"+path.lstrip("/")
def project_url(): return quote(PROJECT,safe="")
def get(path,params=None):
    r=session.get(azure_url(path),params=params,timeout=60); r.raise_for_status(); return r.json()
def post(path,body):
    r=session.post(azure_url(path),params={"api-version":API_VERSION},json=body,timeout=120); r.raise_for_status(); return r.json()
def norm(v): return "".join(c.lower() for c in str(v or "").strip() if c.isalnum())
def fmt_date(v):
    if not v:return None
    try:return datetime.fromisoformat(str(v).replace("Z","+00:00")).strftime("%d %b %Y")
    except:return None
def sort_key(name):
    import re
    m=re.search(r"(\d+)\s*$",str(name)); return (re.sub(r"\d+\s*$","",str(name)).lower(),int(m.group(1)) if m else 10**9)
def sort_status(c):
    d=OrderedDict()
    for s in ORDER:
        if s in c:d[s]=c[s]
    for s in sorted(c):
        if s not in d:d[s]=c[s]
    return list(d.items())
def normalize_type(v):
    v=str(v or "").strip().lower()
    if v in {"user story","product backlog item","requirement"}:return "User Stories"
    if v=="test case":return "Test Cases"
    if v=="bug":return "Bugs"
def get_sprint(v):
    p=[x.strip() for x in str(v or "").split("\\") if x.strip()]; return p[-1] if p else "No Sprint"
def work_ids():
    p=PROJECT.replace("'","''")
    q=f"""SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = '{p}' AND [System.WorkItemType] IN ('User Story','Product Backlog Item','Requirement','Test Case','Bug') AND [System.State] <> 'Removed' ORDER BY [System.IterationPath],[System.Id]"""
    return [x["id"] for x in post(project_url()+"/_apis/wit/wiql",{"query":q}).get("workItems",[])]
def work_items(ids):
    out=[]
    for i in range(0,len(ids),200):
        out += post(project_url()+"/_apis/wit/workitemsbatch",{"ids":ids[i:i+200],"fields":["System.Id","System.Title","System.WorkItemType","System.State","System.IterationPath","System.AssignedTo","System.ChangedDate"]}).get("value",[])
    return out
DETAIL_ITEMS=[]
def load_data():
    global DETAIL_ITEMS
    DETAIL_ITEMS=[]
    raw=OrderedDict()
    for item in work_items(work_ids()):
        f=item.get("fields",{}); cat=normalize_type(f.get("System.WorkItemType")); sprint=get_sprint(f.get("System.IterationPath")); state=str(f.get("System.State","Unknown")).strip()
        if not cat or sprint=="No Sprint":continue
        assigned=f.get("System.AssignedTo")
        if isinstance(assigned,dict):
            assigned=assigned.get("displayName") or assigned.get("uniqueName") or ""
        DETAIL_ITEMS.append({
            "id": item.get("id"),
            "title": str(f.get("System.Title") or ""),
            "type": cat,
            "state": state,
            "sprint": sprint,
            "assignedTo": str(assigned or "Unassigned"),
            "updated": fmt_date(f.get("System.ChangedDate")) or "",
            "url": COLLECTION_URL.rstrip("/") + "/" + quote(PROJECT,safe="") + "/_workitems/edit/" + str(item.get("id"))
        })
        raw.setdefault(sprint,{"User Stories":Counter(),"Test Cases":Counter(),"Bugs":Counter()})[cat][state]+=1
    return OrderedDict((s,{k:sort_status(v) for k,v in sec.items()}) for s,sec in raw.items())
def iteration_dates():
    try:r=get(project_url()+"/_apis/wit/classificationnodes/Iterations",{"$depth":20,"api-version":API_VERSION})
    except:return {}
    d={}
    def walk(n):
        a=n.get("attributes") or {}; name=str(n.get("name") or "").strip()
        if name:d[norm(name)]={"start":fmt_date(a.get("startDate")),"finish":fmt_date(a.get("finishDate"))}
        for c in n.get("children") or []:walk(c)
    walk(r);return d
def overall(data,section):
    c=Counter()
    for sp in data.values():
        for s,n in sp.get(section,[]):c[s]+=n
    return OrderedDict(sort_status(c))
def total(d):return sum(d.values())
def phase(di):
    try:
        s=datetime.strptime(di.get("start") or "","%d %b %Y"); f=datetime.strptime(di.get("finish") or "","%d %b %Y"); t=datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
        return "Active" if s<=t<=f else ("Upcoming" if t<s else "Completed")
    except:return ""
def esc(s):return html.escape(str(s))
def status_rows(items, category="", sprint=""):
    if not items:return '<div class="empty">— No items</div>'
    return ''.join(
        f'<div class="status-row"><span><i style="background:{COLORS.get(s,"#98A2B3")}"></i>{esc(s)}</span>'
        f'<b class="drill-count" data-type="{esc(category)}" data-state="{esc(s)}" data-sprint="{esc(sprint)}" '
        f'onclick="openWorkItemDrilldown(this.dataset.type,this.dataset.state,this.dataset.sprint)">{n:,}</b></div>'
        for s,n in items
    )
def donut_gradient(data):
    t=sum(data.values()); cur=0; parts=[]
    if not t:return "#e8edf3 0 100%"
    for s,n in data.items():
        a=cur/t*100;cur+=n;b=cur/t*100;parts.append(f'{COLORS.get(s,"#98A2B3")} {a:.2f}% {b:.2f}%')
    return ','.join(parts)
def overall_html(title,data,accent,icon,scope):
    t=total(data); rows=''.join(f'<div class="overall-row"><span><i style="background:{COLORS.get(s,"#98A2B3")}"></i>{esc(s)}</span><b>{n:,}</b><div class="mini"><em style="width:{(n/t*100 if t else 0):.1f}%;background:{COLORS.get(s,"#98A2B3")}"></em></div><small>{(n/t*100 if t else 0):.1f}%</small></div>' for s,n in data.items())
    return f'''<section class="overall-card" style="--accent:{accent}"><div class="overall-head"><div><span class="small-icon">{icon}</span><strong>{title}</strong><small>{scope}</small></div><div class="overall-total">Total <b>{t:,}</b></div></div><div class="overall-body"><div class="donut" style="background:conic-gradient({donut_gradient(data)})"><div><b>{t:,}</b><span>Total</span></div></div><div class="overall-rows">{rows}</div></div></section>'''
def create(data,dates):
    project_tokens={norm(PROJECT),norm(PROJECT_DISPLAY_NAME)}
    sprints=OrderedDict(sorted(((n,v) for n,v in data.items() if norm(n) not in project_tokens),key=lambda x:sort_key(x[0])))
    stories=overall(sprints,"User Stories"); bugs=overall(data,"Bugs"); eligible=OrderedDict((n,v) for n,v in sprints.items() if sum(c for _,c in v.get("Test Cases",[]))>0); tests=overall(eligible,"Test Cases")
    cards=[]
    for name,sp in sprints.items():
        st=sum(c for _,c in sp["User Stories"]);tt=sum(c for _,c in sp["Test Cases"]);bt=sum(c for _,c in sp["Bugs"]);di=dates.get(norm(name),{});ph=phase(di)
        dr=(f'{di.get("start")} – {di.get("finish")}' if di.get("start") and di.get("finish") else "Dates not set")
        cards.append(f'''<article class="sprint-card"><div class="sprint-accent"></div><div class="sprint-head"><div><h3>{esc(name)}</h3><span class="phase {ph.lower()}">✓ {ph or "Sprint"}</span></div><b>{st+tt+bt:,} Total Items</b></div><div class="date">▣ {esc(dr)}</div><div class="sprint-cols"><div><h4>▤ User Stories <strong class="drill-count" data-type="User Stories" data-sprint="{esc(name)}" onclick="openWorkItemDrilldown(this.dataset.type,'',this.dataset.sprint)">{st:,}</strong></h4>{status_rows(sp["User Stories"],"User Stories",name)}</div><div><h4>☑ Test Cases <strong class="drill-count" data-type="Test Cases" data-sprint="{esc(name)}" onclick="openWorkItemDrilldown(this.dataset.type,'',this.dataset.sprint)">{tt:,}</strong></h4>{status_rows(sp["Test Cases"],"Test Cases",name)}</div><div><h4>♟ Bugs <strong class="drill-count" data-type="Bugs" data-sprint="{esc(name)}" onclick="openWorkItemDrilldown(this.dataset.type,'',this.dataset.sprint)">{bt:,}</strong></h4>{status_rows(sp["Bugs"],"Bugs",name)}</div></div></article>''')
    updated=datetime.now().strftime("%d %b %Y • %I:%M %p")
    html_text=TEMPLATE.replace("{{WORK_ITEMS_JSON}}",json.dumps(DETAIL_ITEMS,ensure_ascii=False).replace("</","<\\/")).replace("{{PROJECT}}",esc(PROJECT_DISPLAY_NAME)).replace("{{UPDATED}}",updated).replace("{{SPRINTS}}",str(len(eligible))).replace("{{DELIVERY}}",str(len(sprints))).replace("{{STORIES}}",f'{total(stories):,}').replace("{{TESTS}}",f'{total(tests):,}').replace("{{BUGS}}",f'{total(bugs):,}').replace("{{SPRINT_CARDS}}",''.join(cards)).replace("{{OVERALL}}",overall_html("User Stories",stories,"#6941C6","▤","Sprint items only")+overall_html("Test Cases",tests,"#039855","☑","QA sprints only")+overall_html("Bugs",bugs,"#D92D20","♟","Project-wide"))
    with open(OUTPUT_FILE,"w",encoding="utf-8") as f:f.write(html_text)
    print(os.path.abspath(OUTPUT_FILE))

TEMPLATE=r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QA Status Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#101828;font-family:Inter,Segoe UI,Arial,sans-serif}.app{display:flex;min-height:100vh}.sidebar{width:220px;background:#fff;border-right:1px solid #e4e7ec;padding:25px 16px;position:fixed;inset:0 auto 0 0}.brand{font-weight:800;font-size:21px;margin:4px 10px 2px}.brand-sub{font-size:11px;color:#475467;margin:0 10px 28px}.nav a{display:block;padding:13px 14px;margin:5px 0;border-radius:10px;color:#344054;text-decoration:none}.nav a.active{background:#eaf2ff;color:#175cd3;font-weight:700}.main{margin-left:220px;width:calc(100% - 220px);padding:24px 26px 18px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.top h1{margin:0;font-size:30px}.subtitle{color:#667085;margin-top:5px}.actions{display:flex;align-items:center;gap:10px}.updated{text-align:right;color:#667085;font-size:12px;margin-right:10px}.btn{border:1px solid #d0d5dd;background:#fff;padding:10px 14px;border-radius:9px;font-weight:700;cursor:pointer;color:#344054}.btn.primary{background:#175cd3;color:#fff;border-color:#175cd3}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.kpi{background:#fff;border:1px solid #e4e7ec;border-radius:14px;padding:18px;display:flex;gap:14px;align-items:center;box-shadow:0 4px 18px rgba(16,24,40,.035)}.kpi .ico{width:48px;height:48px;border-radius:12px;display:grid;place-items:center;font-size:23px}.kpi label{font-size:12px;font-weight:700}.kpi b{font-size:31px;display:block}.kpi small{color:#667085}.section-title{display:flex;justify-content:space-between;align-items:end;margin:25px 0 12px}.section-title h2{font-size:20px;margin:0}.section-title p{margin:3px 0 0;color:#667085;font-size:12px}.sprints{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.sprint-card,.overall-card{position:relative;background:#fff;border:1px solid #e4e7ec;border-radius:14px;overflow:hidden;box-shadow:0 4px 16px rgba(16,24,40,.03)}.sprint-card{padding:17px}.sprint-accent{position:absolute;left:0;right:0;top:0;height:4px;background:linear-gradient(90deg,#175cd3,#6941c6)}.sprint-head,.sprint-head>div{display:flex;justify-content:space-between;align-items:center;gap:10px}.sprint-head h3{margin:0;font-size:17px}.sprint-head>b{font-size:11px;color:#667085}.phase{font-size:10px;padding:4px 8px;border-radius:20px;background:#ecfdf3;color:#027a48;font-weight:700}.phase.upcoming{background:#f2f4f7;color:#475467}.phase.active{background:#fffaeb;color:#b54708}.date{font-size:11px;color:#667085;margin:9px 0 12px}.sprint-cols{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid #eaecf0}.sprint-cols>div{padding:12px}.sprint-cols>div+div{border-left:1px solid #eaecf0}.sprint-cols h4{font-size:11px;margin:0 0 10px;color:#344054}.sprint-cols h4 strong{float:right;font-size:17px;color:#101828}.status-row{display:flex;justify-content:space-between;font-size:11px;margin:7px 0}.status-row span{display:flex;align-items:center;gap:6px}.status-row i,.overall-row i{width:7px;height:7px;border-radius:50%;display:inline-block}.empty{font-size:11px;color:#98a2b3}.overall-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.overall-card{padding:16px;border-top:4px solid var(--accent)}.overall-head{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #eaecf0;padding-bottom:11px}.overall-head>div:first-child{display:flex;align-items:center;gap:8px}.overall-head small{color:#667085;font-size:9px}.small-icon{background:#f2f4f7;border-radius:7px;padding:5px}.overall-total{font-size:11px;color:#667085}.overall-total b{font-size:20px;color:#101828;margin-left:4px}.overall-body{display:grid;grid-template-columns:120px 1fr;gap:18px;align-items:center;padding-top:15px}.donut{width:105px;height:105px;border-radius:50%;display:grid;place-items:center}.donut>div{width:65px;height:65px;background:#fff;border-radius:50%;display:grid;place-items:center;align-content:center}.donut b{font-size:20px}.donut span{font-size:9px;color:#667085}.overall-row{display:grid;grid-template-columns:90px 35px 1fr 42px;gap:7px;align-items:center;font-size:10px;margin:7px 0}.overall-row span{display:flex;align-items:center;gap:6px}.mini{height:6px;background:#eaecf0;border-radius:5px;overflow:hidden}.mini em{display:block;height:100%;border-radius:5px}.overall-row small{text-align:right;color:#667085}.footer{display:flex;justify-content:space-between;color:#667085;font-size:10px;padding:24px 2px 5px}@media(max-width:1100px){.sidebar{display:none}.main{margin-left:0;width:100%}.kpis,.overall-grid{grid-template-columns:repeat(2,1fr)}.sprints{grid-template-columns:1fr}}
</style>
<style id="v23-export-fixes">
  /* V23: export-safe layout */
  .overall-card { min-width: 0; overflow: hidden; }
  .overall-card .status-row {
      display: grid;
      grid-template-columns: minmax(64px,1fr) 38px minmax(54px,.9fr) 44px;
      gap: 5px;
      align-items: center;
  }
  .overall-card .status-percent {
      min-width: 42px;
      text-align: right;
      white-space: nowrap;
  }
  body.exporting .actions,
  body.exporting .export-actions,
  body.exporting .export-btn,
  body.exporting button,
  body.exporting .no-export {
      display: none !important;
  }
  body.exporting .sprint-card { min-height: 0 !important; }
  body.exporting .overall-card { overflow: visible !important; }
  body.exporting .overall-grid {
      grid-template-columns: repeat(3, minmax(0,1fr)) !important;
  }
</style>


<style id="v24-pdf-overall-alignment-fix">
/* Applied only while Export PDF is capturing the V24 dashboard. */
body.exporting #dashboard .overall-card{overflow:hidden!important}
body.exporting #dashboard .overall-body{
  grid-template-columns:110px minmax(0,1fr)!important;
  column-gap:12px!important;
  min-width:0!important;
}
body.exporting #dashboard .overall-list{min-width:0!important;width:100%!important;overflow:hidden!important}
body.exporting #dashboard .overall-row{
  box-sizing:border-box!important;
  width:100%!important;
  min-width:0!important;
  grid-template-columns:minmax(58px,1fr) 28px minmax(46px,.8fr) 40px!important;
  gap:5px!important;
  align-items:center!important;
}
body.exporting #dashboard .overall-row > *{min-width:0!important}
body.exporting #dashboard .overall-row small{
  width:40px!important;
  max-width:40px!important;
  text-align:right!important;
  justify-self:end!important;
  white-space:nowrap!important;
  overflow:visible!important;
}
body.exporting #dashboard .mini{min-width:30px!important;width:100%!important}
</style>




<style id="v32-drilldown-css">
.drill-count{cursor:pointer}.drill-count:hover{color:#175cd3!important;text-decoration:underline}
.wi-modal{position:fixed;inset:0;z-index:9999;display:none}.wi-modal.open{display:block}.wi-backdrop{position:absolute;inset:0;background:rgba(16,24,40,.48)}
.wi-panel{position:absolute;right:0;top:0;height:100%;width:min(1150px,92vw);background:#fff;box-shadow:-18px 0 40px rgba(16,24,40,.18);display:flex;flex-direction:column}
.wi-head{display:flex;justify-content:space-between;padding:28px 30px 18px;border-bottom:1px solid #eaecf0}.wi-head h2{margin:0;font-size:27px}.wi-head p{margin:6px 0 0;color:#667085;font-size:13px}
.wi-close{border:0;background:#f2f4f7;border-radius:11px;width:44px;height:44px;font-size:24px;cursor:pointer}
.wi-filterbar{padding:16px 30px;border-bottom:1px solid #eaecf0;display:grid;grid-template-columns:minmax(280px,1fr) 170px 190px auto;gap:10px;align-items:center}
.wi-input,.wi-select{border:1px solid #d0d5dd;border-radius:9px;padding:11px 13px;background:#fff;color:#344054}.wi-count{text-align:right;font-size:12px;font-weight:800;color:#667085}
.wi-context{padding:9px 30px;background:#f9fafb;color:#475467;font-size:11px;border-bottom:1px solid #eaecf0}.wi-table-wrap{overflow:auto;flex:1;padding:0 30px}
.wi-table{width:100%;border-collapse:collapse;font-size:12px;min-width:900px}.wi-table th,.wi-table td{padding:12px 10px;border-bottom:1px solid #eaecf0;text-align:left}
.wi-table th{position:sticky;top:0;background:#f9fafb;z-index:2;color:#475467;cursor:pointer}.wi-id{font-weight:800;color:#175cd3;text-decoration:none}.wi-title{min-width:360px}
.wi-state{display:inline-flex;align-items:center;gap:7px}.wi-state i{width:8px;height:8px;border-radius:50%}.wi-footer{padding:12px 30px;border-top:1px solid #eaecf0;display:flex;justify-content:space-between;align-items:center;gap:12px;color:#667085;font-size:11px}
.wi-pages{display:flex;gap:5px}.wi-page{border:1px solid #d0d5dd;background:#fff;border-radius:7px;min-width:31px;height:30px;cursor:pointer}.wi-page.active{background:#175cd3;color:#fff;border-color:#175cd3}.wi-page:disabled{opacity:.4}
.wi-export{border:1px solid #d0d5dd;background:#fff;border-radius:8px;padding:8px 11px;font-weight:700;cursor:pointer}body.exporting .wi-modal{display:none!important}
</style></head><body><div class="app"><aside class="sidebar"><div class="brand">Red Sea</div><div class="brand-sub">Whistleblowing Management System</div><nav class="nav"><a class="active">⌂ &nbsp; Overview</a><a>◇ &nbsp; Sprints</a><a>▤ &nbsp; User Stories</a><a>☑ &nbsp; Test Cases</a><a>♟ &nbsp; Bugs</a><a>▥ &nbsp; Reports</a></nav></aside><main class="main" id="dashboard"><header class="top"><div><h1>QA Status Dashboard</h1><div class="subtitle">Azure DevOps &nbsp; | &nbsp; QA Execution Overview</div></div><div class="actions"><div class="updated">Updated<br><b>{{UPDATED}}</b></div><button class="btn" onclick="exportImage()">↧ Export Image</button><button class="btn primary" onclick="exportPDF()">↧ Export PDF</button></div></header><section class="kpis"><div class="kpi"><span class="ico" style="background:#f4ebff;color:#6941c6">◇</span><div><label>Sprints</label><b>{{SPRINTS}}</b><small>{{SPRINTS}} out of {{DELIVERY}} delivery iterations</small></div></div><div class="kpi"><span class="ico" style="background:#eaf2ff;color:#175cd3">▤</span><div><label>User Stories</label><b>{{STORIES}}</b><small>Total sprint user stories</small></div></div><div class="kpi"><span class="ico" style="background:#e7f8f0;color:#039855">☑</span><div><label>Test Cases</label><b>{{TESTS}}</b><small>Total QA test cases</small></div></div><div class="kpi"><span class="ico" style="background:#feeceb;color:#d92d20">♟</span><div><label>Bugs</label><b>{{BUGS}}</b><small>Total project bugs</small></div></div></section><div class="section-title"><div><h2>Sprint Details</h2><p>User Stories, Test Cases and Bugs by sprint</p></div></div><section class="sprints">{{SPRINT_CARDS}}</section><div class="section-title"><div><h2>Overall Status</h2><p>Total status count across the project</p></div></div><section class="overall-grid">{{OVERALL}}</section>
<footer class="footer"><span>{{PROJECT}} &nbsp; | &nbsp; QA Dashboard</span><span>Generated from Azure DevOps</span></footer></main></div><div class="wi-modal" id="wiModal"><div class="wi-backdrop" onclick="closeWorkItemDrilldown()"></div><section class="wi-panel">
<div class="wi-head"><div><h2 id="wiModalTitle">Work Item Details</h2><p>Azure DevOps work-item drill-down</p></div><button class="wi-close" onclick="closeWorkItemDrilldown()">×</button></div>
<div class="wi-filterbar"><input class="wi-input" id="wiSearch" placeholder="Search ID, title or assigned to..." oninput="wiSetSearch(this.value)">
<select class="wi-select" id="wiStateFilter" onchange="wiSetState(this.value)"><option value="">All States</option></select>
<select class="wi-select" id="wiAssignedFilter" onchange="wiSetAssigned(this.value)"><option value="">All Assignees</option></select><div class="wi-count" id="wiCount"></div></div>
<div class="wi-context" id="wiContext"></div><div class="wi-table-wrap"><table class="wi-table"><thead><tr><th onclick="wiSort('id')">ID ↕</th><th onclick="wiSort('title')">Title ↕</th><th onclick="wiSort('state')">State ↕</th><th onclick="wiSort('assignedTo')">Assigned To ↕</th><th onclick="wiSort('updated')">Updated ↕</th></tr></thead><tbody id="wiBody"></tbody></table></div>
<div class="wi-footer"><span id="wiShowing"></span><div style="display:flex;gap:10px;align-items:center"><button class="wi-export" onclick="wiExportCSV()">Export CSV</button><div class="wi-pages" id="wiPages"></div><select class="wi-select" onchange="wiSetPageSize(this.value)"><option value="10">10 / page</option><option value="25" selected>25 / page</option><option value="50">50 / page</option><option value="100">100 / page</option></select></div></div>
</section></div>

<script>window.V24_WORK_ITEMS={{WORK_ITEMS_JSON}};</script>


<script id="v32-drilldown-js">
const WIC={'New':'#6941C6','Open':'#D92D20','Active':'#1570EF','In Progress':'#1570EF','Passed':'#039855','Done':'#039855','Closed':'#039855','Failed':'#D92D20','Fails':'#D92D20','Blocked':'#DC6803','Block':'#DC6803','Resolved':'#DC6803','Re-Open':'#98A2B3'};
let wb={type:'',state:'',sprint:''},ws='',wstate='',wa='',wp=1,wps=25,wsk='id',wsd=1;
function we(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function baseRows(){return (window.V24_WORK_ITEMS||[]).filter(x=>(!wb.type||x.type===wb.type)&&(!wb.state||x.state===wb.state)&&(!wb.sprint||x.sprint===wb.sprint));}
function filtered(){let q=ws.trim().toLowerCase();return baseRows().filter(x=>(!wstate||x.state===wstate)&&(!wa||x.assignedTo===wa)&&(!q||[x.id,x.title,x.state,x.assignedTo].some(v=>String(v??'').toLowerCase().includes(q)))).sort((a,b)=>{let av=a[wsk]??'',bv=b[wsk]??'';if(wsk==='id'){av=+av;bv=+bv}return(av<bv?-1:av>bv?1:0)*wsd})}
function openWorkItemDrilldown(type='',state='',sprint=''){wb={type,state,sprint};ws='';wp=1;document.getElementById('wiSearch').value='';document.getElementById('wiModalTitle').textContent=type||'Work Item Details';document.getElementById('wiContext').textContent=[type,state,sprint].filter(Boolean).join(' / ')||'All work items';let b=baseRows();document.getElementById('wiStateFilter').innerHTML='<option value="">All States</option>'+[...new Set(b.map(x=>x.state))].sort().map(v=>`<option>${we(v)}</option>`).join('');document.getElementById('wiAssignedFilter').innerHTML='<option value="">All Assignees</option>'+[...new Set(b.map(x=>x.assignedTo))].sort().map(v=>`<option>${we(v)}</option>`).join('');wstate='';wa='';document.getElementById('wiModal').classList.add('open');document.body.style.overflow='hidden';renderWI()}
function closeWorkItemDrilldown(){document.getElementById('wiModal').classList.remove('open');document.body.style.overflow=''}
function wiSetSearch(v){ws=v;wp=1;renderWI()}function wiSetState(v){wstate=v;wp=1;renderWI()}function wiSetAssigned(v){wa=v;wp=1;renderWI()}function wiSetPageSize(v){wps=+v;wp=1;renderWI()}
function wiSort(k){if(wsk===k)wsd*=-1;else{wsk=k;wsd=1}wp=1;renderWI()}function wiGoPage(p){wp=p;renderWI()}
function renderWI(){let a=filtered(),pages=Math.max(1,Math.ceil(a.length/wps));wp=Math.max(1,Math.min(wp,pages));let st=(wp-1)*wps,r=a.slice(st,st+wps);document.getElementById('wiCount').textContent=`${a.length} work items`;document.getElementById('wiShowing').textContent=a.length?`Showing ${st+1}-${Math.min(st+wps,a.length)} of ${a.length}`:'0 work items';document.getElementById('wiBody').innerHTML=r.length?r.map(x=>`<tr><td><a class="wi-id" href="${we(x.url)}" target="_blank">${we(x.id)}</a></td><td class="wi-title">${we(x.title)}</td><td><span class="wi-state"><i style="background:${WIC[x.state]||'#98A2B3'}"></i>${we(x.state)}</span></td><td>${we(x.assignedTo)}</td><td>${we(x.updated)}</td></tr>`).join(''):'<tr><td colspan="5" style="text-align:center;padding:30px;color:#98a2b3">No work items found</td></tr>';let h=`<button class="wi-page" ${wp===1?'disabled':''} onclick="wiGoPage(${wp-1})">‹</button>`;for(let p=Math.max(1,wp-2);p<=Math.min(pages,wp+2);p++)h+=`<button class="wi-page ${p===wp?'active':''}" onclick="wiGoPage(${p})">${p}</button>`;h+=`<button class="wi-page" ${wp===pages?'disabled':''} onclick="wiGoPage(${wp+1})">›</button>`;document.getElementById('wiPages').innerHTML=h}
function wiExportCSV(){let a=filtered(),q=v=>'"'+String(v??'').replace(/"/g,'""')+'"',csv=['ID,Title,Type,State,Sprint,Assigned To,Updated,URL',...a.map(x=>[x.id,x.title,x.type,x.state,x.sprint,x.assignedTo,x.updated,x.url].map(q).join(','))].join('\r\n'),l=document.createElement('a');l.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));l.download='QA_Work_Items_Filtered.csv';l.click()}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeWorkItemDrilldown()});
</script><script>
async function capture(){const el=document.getElementById('dashboard');return await html2canvas(el,{scale:2,useCORS:true,backgroundColor:'#f4f7fb',windowWidth:el.scrollWidth,windowHeight:el.scrollHeight});}

async function exportPDF() {
    const button = document.querySelector('button[onclick="exportPDF()"]');
    const originalText = button ? button.innerHTML : '';
    try {
        if (button) { button.disabled = true; button.innerHTML = 'Generating PDF...'; }
        if (typeof html2canvas === 'undefined') throw new Error('html2canvas library did not load.');
        if (!window.jspdf || !window.jspdf.jsPDF) throw new Error('jsPDF library did not load.');

        const target = document.getElementById('dashboard');
        if (!target) throw new Error('Dashboard element was not found.');

        /* Export V24 exactly as displayed; only action buttons are hidden during capture. */
        document.body.classList.add('exporting');
        const restoreDonuts = v24PrepareDonutsForPdf();
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

        const canvas = await html2canvas(target, {
            scale: 2.5,
            useCORS: true,
            allowTaint: false,
            backgroundColor: '#F4F7FB',
            logging: false,
            scrollX: 0,
            scrollY: -window.scrollY,
            width: target.scrollWidth,
            height: target.scrollHeight,
            windowWidth: target.scrollWidth,
            windowHeight: target.scrollHeight
        });

        const { jsPDF } = window.jspdf;
        /* Preserve the dashboard aspect ratio instead of forcing a print layout. */
        const pageWidth = 420;
        const pageHeight = pageWidth * canvas.height / canvas.width;
        const pdf = new jsPDF({orientation:'landscape', unit:'mm', format:[pageWidth,pageHeight], compress:true});
        pdf.addImage(canvas.toDataURL('image/jpeg',0.98),'JPEG',0,0,pageWidth,pageHeight,undefined,'FAST');

        const now=new Date(), pad=n=>String(n).padStart(2,'0');
        const stamp=`${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}_${pad(now.getHours())}${pad(now.getMinutes())}`;
        pdf.save(`QA_Status_Dashboard_V24_${stamp}.pdf`);
        restoreDonuts();
    } catch (error) {
        console.error('PDF export failed:', error);
        alert('PDF export failed.\n\n' + (error?.message || error));
    } finally {
        document.body.classList.remove('exporting');
        if (button) { button.disabled = false; button.innerHTML = originalText; }
    }
}

async function exportImage() {
    const target =
        document.getElementById('dashboard') ||
        document.querySelector('.dashboard') ||
        document.querySelector('main') ||
        document.body;

    const now = new Date();
    const pad = n => String(n).padStart(2, '0');
    const stamp =
        `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())}_` +
        `${pad(now.getHours())}${pad(now.getMinutes())}`;
    const filename = `QA_Status_Dashboard_${stamp}.png`;

    document.body.classList.add('exporting');

    try {
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const canvas = await html2canvas(target, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#F6F8FB',
            logging: false,
            windowWidth: target.scrollWidth,
            windowHeight: target.scrollHeight
        });
        const link = document.createElement('a');
        link.download = filename;
        link.href = canvas.toDataURL('image/png');
        link.click();
    } finally {
        document.body.classList.remove('exporting');
    }
}

</script>

<script id="v24-pdf-donut-fix">
/* Build PDF donuts from the visible Overall Status values, not from conic-gradient parsing. */
function v24BuildSvgDonut(donut){
    const card=donut.closest('.overall-card');
    if(!card) return null;
    const rows=[...card.querySelectorAll('.overall-row')];
    const items=rows.map(row=>{
        const dot=row.querySelector('i');
        const valueEl=row.querySelector('b');
        const value=Number((valueEl?.textContent||'0').replace(/[^0-9.-]/g,''))||0;
        const color=dot ? getComputedStyle(dot).backgroundColor : '#98A2B3';
        return {value,color};
    }).filter(x=>x.value>0);
    const total=items.reduce((s,x)=>s+x.value,0);
    if(!total) return null;

    const size=Math.max(donut.offsetWidth,donut.offsetHeight,105);
    const cx=size/2,cy=size/2,r=size*.39,stroke=size*.19,C=2*Math.PI*r;
    const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.setAttribute('width',size); svg.setAttribute('height',size);
    svg.setAttribute('viewBox',`0 0 ${size} ${size}`);
    Object.assign(svg.style,{position:'absolute',inset:'0',width:'100%',height:'100%',transform:'rotate(-90deg)',transformOrigin:'50% 50%',zIndex:'1'});

    let used=0;
    items.forEach(item=>{
        const pct=item.value/total;
        const c=document.createElementNS('http://www.w3.org/2000/svg','circle');
        c.setAttribute('cx',cx); c.setAttribute('cy',cy); c.setAttribute('r',r);
        c.setAttribute('fill','none'); c.setAttribute('stroke',item.color); c.setAttribute('stroke-width',stroke);
        c.setAttribute('stroke-dasharray',`${C*pct} ${C*(1-pct)}`);
        c.setAttribute('stroke-dashoffset',`${-C*used}`);
        c.setAttribute('stroke-linecap','butt');
        svg.appendChild(c); used+=pct;
    });

    const center=donut.querySelector(':scope > div');
    donut.dataset.v24OldBackground=donut.style.background||'';
    donut.style.position='relative'; donut.style.background='transparent';
    if(center){center.style.position='relative';center.style.zIndex='2';}
    donut.insertBefore(svg,donut.firstChild);
    return {svg,center};
}
function v24PrepareDonutsForPdf(){
    const changes=[];
    document.querySelectorAll('#dashboard .donut').forEach(d=>{
        const made=v24BuildSvgDonut(d);
        if(made) changes.push({d,...made,oldBackground:d.dataset.v24OldBackground||''});
    });
    return ()=>changes.forEach(x=>{
        x.svg.remove();
        x.d.style.background=x.oldBackground;
        delete x.d.dataset.v24OldBackground;
        if(x.center){x.center.style.position='';x.center.style.zIndex='';}
    });
}
</script>

</body></html>'''

def main():
    print("QA Status Dashboard")
    print("-------------------")
    print("Configuration: loading .env")

    if not validate_pat():
        sys.exit(2)

    print("PAT Configuration: PASS")
    print("Testing Azure DevOps authentication...")
    if not test_azure_auth():
        sys.exit(3)

    try:
        print("Loading latest dashboard data...")
        data = load_data()
        create(data, iteration_dates())
        print("Dashboard Update: PASS")
        print("HTML:", os.path.abspath(OUTPUT_FILE))
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "Unknown"
        print(f"Dashboard Update: FAILED (HTTP {code})")
        print(str(e))
        sys.exit(4)
    except Exception as e:
        print("Dashboard Update: FAILED")
        print(repr(e))
        sys.exit(5)

if __name__=='__main__':
    main()
