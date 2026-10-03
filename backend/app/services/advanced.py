import json, statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

def aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts

def meta(e):
    try: return json.loads(e.metadata_json or "{}")
    except Exception: return {}

def label(e):
    if e.event_type == "screen_context":
        return meta(e).get("category") or "unknown"
    return e.application or e.project or e.event_type

def sessions(events, gap_minutes=10):
    rows=sorted([e for e in events if e.event_type=="application_usage" and e.application], key=lambda e: aware(e.timestamp))
    out=[]; cur=None; start=None; last=None
    for e in rows:
        ts=aware(e.timestamp)
        if cur != e.application or (last and ts-last > timedelta(minutes=gap_minutes)):
            if cur and start and last:
                sec=(last-start).total_seconds()
                if 15 <= sec <= 8*3600: out.append({"application":cur,"start":start,"end":last,"seconds":sec})
            cur=e.application; start=ts
        last=ts
    if cur and start and last:
        sec=(last-start).total_seconds()
        if 15 <= sec <= 8*3600: out.append({"application":cur,"start":start,"end":last,"seconds":sec})
    return out

def daily_brief(events, days=1):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    rows=[e for e in events if aware(e.timestamp)>=cutoff]
    ss=sessions(rows)
    apps=Counter(e.application for e in rows if e.application)
    projects=Counter(e.project for e in rows if e.project)
    cats=Counter(meta(e).get("category") for e in rows if e.event_type=="screen_context" and meta(e).get("category"))
    switches=sum(1 for a,b in zip(ss,ss[1:]) if a["application"]!=b["application"])
    return {"window_days":days,"events":len(rows),"active_applications":len(apps),"active_projects":len(projects),"tracked_minutes":round(sum(x["seconds"] for x in ss)/60,1),"deep_work_minutes":round(sum(x["seconds"] for x in ss if x["seconds"]>=1800)/60,1),"context_switches":switches,"top_app":apps.most_common(1)[0][0] if apps else None,"top_project":projects.most_common(1)[0][0] if projects else None,"top_activity":cats.most_common(1)[0][0] if cats else None,"highlights":[{"type":"application","value":k,"count":v} for k,v in apps.most_common(3)]}

def routines(events, days=30):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days)
    buckets=defaultdict(Counter)
    for e in events:
        ts=aware(e.timestamp)
        if ts<cutoff: continue
        l=label(e)
        if not l or l in {"unknown","protected"}: continue
        buckets[(ts.weekday(),ts.hour)][l]+=1
    out=[]
    for (wd,h),c in buckets.items():
        total=sum(c.values()); lab,n=c.most_common(1)[0]
        if total>=3 and n/total>=0.55:
            out.append({"weekday":wd,"hour":h,"label":lab,"observations":total,"dominance":round(n/total,2)})
    return {"available":bool(out),"routines":sorted(out,key=lambda x:(-x["dominance"],-x["observations"]))[:20],"method":"weekday/hour recurrence"}

def project_lifecycle(events, days=180):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days); by=defaultdict(list)
    for e in events:
        ts=aware(e.timestamp)
        if ts>=cutoff and e.project: by[e.project].append(e)
    out=[]
    for p,rows in by.items():
        rows.sort(key=lambda e: aware(e.timestamp)); first=aware(rows[0].timestamp); last=aware(rows[-1].timestamp)
        commits=sum(1 for e in rows if e.event_type=="git_commit")
        files=sum(1 for e in rows if e.event_type in {"file_activity","project_activity"})
        active_days=len({aware(e.timestamp).date() for e in rows})
        age=(datetime.now(timezone.utc)-last).total_seconds()/86400
        if commits==0 and files==0: phase="discovered"
        elif age>14: phase="dormant"
        elif commits>=5 and active_days>=3: phase="active development"
        else: phase="iterating"
        out.append({"project":p,"phase":phase,"first_seen":first.isoformat(),"last_seen":last.isoformat(),"active_days":active_days,"commits":commits,"file_events":files,"signals":len(rows)})
    return {"projects":sorted(out,key=lambda x:x["signals"],reverse=True)}

def context_switches(events, limit=20):
    ss=sessions(events); c=Counter()
    for a,b in zip(ss,ss[1:]):
        if a["application"]!=b["application"]:
            c[(a["application"],b["application"])] += 1
    return {"switches": [{"from":a,"to":b,"count":n} for (a,b),n in c.most_common(limit)],"total":sum(c.values())}

def data_quality(events, days=7):
    cutoff=datetime.now(timezone.utc)-timedelta(days=days); rows=[e for e in events if aware(e.timestamp)>=cutoff]
    byday=Counter(aware(e.timestamp).date().isoformat() for e in rows)
    sources=Counter(e.source for e in rows); types=Counter(e.event_type for e in rows)
    dates=[cutoff.date()+timedelta(days=i) for i in range(days+1)]
    active=sum(1 for d in dates if d.isoformat() in byday)
    gaps=max(0,len(dates)-active)
    score=max(0,min(100,round((active/max(1,len(dates)))*100)))
    return {"score":score,"events":len(rows),"active_days":active,"gap_days":gaps,"sources":dict(sources),"event_types":dict(types),"window_days":days}

def search_events(events, q, limit=50):
    q=(q or "").strip().lower()
    if not q: return []
    out=[]
    for e in sorted(events,key=lambda x:aware(x.timestamp),reverse=True):
        hay=" ".join(str(x or "") for x in [e.event_type,e.source,e.project,e.application])
        if q in hay.lower(): out.append({"id":e.id,"timestamp":aware(e.timestamp).isoformat(),"event_type":e.event_type,"source":e.source,"project":e.project,"application":e.application})
        if len(out)>=limit: break
    return out
