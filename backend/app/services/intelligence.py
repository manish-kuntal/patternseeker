import json, math, statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


def aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


def meta(e):
    try: return json.loads(e.metadata_json or "{}")
    except Exception: return {}


def screen_category(e):
    m=meta(e); return m.get("category") or "unknown"


def app_events(events):
    return [e for e in events if e.event_type == "application_usage" and e.application]


def screen_events(events):
    return [e for e in events if e.event_type == "screen_context"]


def sessions(events, gap_minutes=10):
    rows=sorted(app_events(events), key=lambda e: aware(e.timestamp))
    out=[]; cur=None; start=None; last=None
    for e in rows:
        ts=aware(e.timestamp); app=e.application
        if cur != app or (last and ts-last > timedelta(minutes=gap_minutes)):
            if cur and start and last:
                sec=(last-start).total_seconds()
                if 15 <= sec <= 8*3600: out.append({"application":cur,"start":start,"end":last,"seconds":sec})
            cur, start = app, ts
        last=ts
    if cur and start and last:
        sec=(last-start).total_seconds()
        if 15 <= sec <= 8*3600: out.append({"application":cur,"start":start,"end":last,"seconds":sec})
    return out


def behavior_graph(events, limit_nodes=40, limit_edges=80):
    nodes={}; edges=Counter(); node_types={}
    def add_node(key,label,typ):
        if key not in nodes:
            nodes[key]={"id":key,"label":label[:80],"type":typ,"weight":0}; node_types[key]=typ
        nodes[key]["weight"]+=1
    seq=[]
    for e in sorted(events,key=lambda x: aware(x.timestamp)):
        if e.event_type=="application_usage" and e.application:
            key="app:"+e.application.lower(); add_node(key,e.application,"application"); seq.append(key)
        elif e.event_type=="screen_context":
            c=screen_category(e)
            if c not in {"unknown","protected"}:
                key="activity:"+c; add_node(key,c.replace("_"," ").title(),"activity"); seq.append(key)
        elif e.project and e.event_type in {"project_activity","file_activity","git_commit","project_discovered"}:
            key="project:"+e.project.lower(); add_node(key,e.project,"project"); seq.append(key)
    compact=[]
    for x in seq:
        if not compact or compact[-1]!=x: compact.append(x)
    for a,b in zip(compact,compact[1:]):
        if a!=b: edges[(a,b)]+=1
    ns=sorted(nodes.values(),key=lambda x:x["weight"],reverse=True)[:limit_nodes]
    keep={n["id"] for n in ns}
    es=[{"source":a,"target":b,"weight":w} for (a,b),w in edges.most_common(limit_edges) if a in keep and b in keep]
    return {"nodes":ns,"edges":es,"generated_at":datetime.now(timezone.utc).isoformat()}


def focus_analysis(events):
    ss=sessions(events)
    if not ss: return {"available":False,"message":"Need more foreground application history."}
    total=sum(s["seconds"] for s in ss)
    switches=max(0,len(ss)-1)
    avg_switch_rate=(switches/(total/3600)) if total else 0
    deep=[s for s in ss if s["seconds"]>=30*60]
    deep_seconds=sum(s["seconds"] for s in deep)
    focus_ratio=deep_seconds/total if total else 0
    by_hour=Counter(s["start"].hour for s in ss)
    peak_hour,count=by_hour.most_common(1)[0]
    score=max(0,min(100, round(55 + focus_ratio*45 - min(25,avg_switch_rate*2))))
    return {"available":True,"score":score,"sessions":len(ss),"tracked_minutes":round(total/60,1),"deep_sessions":len(deep),"deep_work_minutes":round(deep_seconds/60,1),"context_switches":switches,"switches_per_hour":round(avg_switch_rate,1),"peak_hour":peak_hour,"peak_hour_sessions":count,"interpretation":"longer uninterrupted sessions with fewer transitions" if score>=70 else "mixed focus with frequent context changes"}


def predictions(events):
    rows=screen_events(events)+app_events(events)
    if len(rows)<12: return {"available":False,"message":"Need more history before recurring activity estimates are reliable.","predictions":[]}
    buckets=defaultdict(Counter); counts=Counter()
    for e in rows:
        ts=aware(e.timestamp); label=None
        if e.event_type=="screen_context": label=screen_category(e)
        elif e.application: label=e.application
        if label and label not in {"unknown","protected"}:
            key=(ts.weekday(),ts.hour); buckets[key][label]+=1; counts[key]+=1
    out=[]
    for key,c in sorted(buckets.items(),key=lambda kv: sum(kv[1].values()),reverse=True)[:12]:
        label,n=c.most_common(1)[0]; total=sum(c.values()); confidence=min(.95,.45+n/max(total,1)*.5)
        out.append({"weekday":key[0],"hour":key[1],"expected":label,"observations":total,"confidence":round(confidence,2)})
    return {"available":bool(out),"predictions":out,"method":"historical weekday/hour recurrence; descriptive estimate, not certainty"}


def anomalies(events, days=30):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    recent=[e for e in events if aware(e.timestamp)>=cutoff]
    daily=Counter(aware(e.timestamp).date().isoformat() for e in recent)
    if len(daily)<5: return {"available":False,"message":"Need at least 5 active days for a baseline.","anomalies":[]}
    vals=list(daily.values()); med=statistics.median(vals); mad=statistics.median([abs(x-med) for x in vals]) or 1
    out=[]
    for day,count in sorted(daily.items(),key=lambda kv:kv[0],reverse=True)[:14]:
        robust=abs(count-med)/(1.4826*mad)
        if robust>=2:
            out.append({"date":day,"metric":"daily_events","value":count,"baseline_median":med,"robust_deviation":round(robust,2),"type":"unusually_high" if count>med else "unusually_low"})
    return {"available":True,"baseline":{"median_daily_events":med,"active_days":len(daily)},"anomalies":out,"method":"median/MAD robust baseline"}
