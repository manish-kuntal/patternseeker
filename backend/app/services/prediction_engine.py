import json, math, statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


def aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


def meta(e):
    try:
        return json.loads(e.metadata_json or "{}")
    except Exception:
        return {}


def label(e):
    if e.event_type == "screen_context":
        return meta(e).get("category") or "unknown"
    return e.application or e.project or e.event_type


def activity_rows(events):
    rows=[]
    for e in events:
        if e.event_type not in {"application_usage", "screen_context", "project_activity", "file_activity", "git_commit"}:
            continue
        l=label(e)
        if l and l not in {"unknown", "protected", "unchanged"}:
            rows.append((aware(e.timestamp), str(l)))
    return sorted(rows)


def _confidence(support, dominance, recency):
    # Confidence is evidence strength, not probability of a guaranteed future event.
    return round(max(0.0, min(0.97, 0.20 + 0.35*min(1,support/12) + 0.30*dominance + 0.15*recency)), 2)


def forecast(events, horizon_hours=24):
    rows=activity_rows(events)
    if len(rows)<12:
        return {"available":False,"message":"Need more historical activity before forecasts can be generated.","next":[],"windows":[]}

    now=datetime.now(timezone.utc)
    slot=defaultdict(Counter)
    slot_dates=defaultdict(set)
    last_seen={}
    for ts,l in rows:
        key=(ts.weekday(),ts.hour)
        slot[key][l]+=1
        slot_dates[key].add(ts.date())
        last_seen[(key,l)] = ts

    # Current and upcoming hourly slots. Rank candidates by historical support, dominance and recency.
    next_items=[]
    for delta in range(0, horizon_hours+1):
        t=now+timedelta(hours=delta)
        key=(t.weekday(),t.hour)
        counts=slot.get(key)
        if not counts: continue
        total=sum(counts.values())
        for l,n in counts.most_common(3):
            support=n
            dominance=n/total
            days=max(1,(now.date()-min(slot_dates[key])).days+1)
            last=last_seen.get((key,l))
            age_days=(now-last).total_seconds()/86400 if last else days
            recency=math.exp(-min(age_days,30)/14)
            conf=_confidence(support,dominance,recency)
            if support>=2 and dominance>=0.35:
                next_items.append({"starts_in_hours":delta,"weekday":t.weekday(),"hour":t.hour,"expected":l,"support":support,"observations":total,"dominance":round(dominance,2),"recency":round(recency,2),"confidence":conf,"basis_days":len(slot_dates[key])})
                break

    # Recurring windows, with entropy so ambiguous slots are not overclaimed.
    windows=[]
    for key,counts in slot.items():
        total=sum(counts.values()); top,n=counts.most_common(1)[0]
        if total<3: continue
        probs=[v/total for v in counts.values()]
        entropy=-sum(p*math.log(p,2) for p in probs)
        dominance=n/total
        support_days=len(slot_dates[key])
        last=last_seen.get((key,top))
        recency=math.exp(-min(((now-last).total_seconds()/86400 if last else 30),30)/14)
        windows.append({"weekday":key[0],"hour":key[1],"expected":top,"support":n,"observations":total,"dominance":round(dominance,2),"entropy":round(entropy,2),"active_days":support_days,"confidence":_confidence(n,dominance,recency)})
    windows.sort(key=lambda x:(x["confidence"],x["support"]),reverse=True)

    return {"available":True,"generated_at":now.isoformat(),"method":"weekday/hour evidence with support, dominance, recency and ambiguity controls","next":next_items[:8],"windows":windows[:20]}


def pattern_candidates(events):
    """Find repeated candidate patterns before they become durable Pattern records."""
    rows=activity_rows(events)
    if len(rows)<15:
        return {"available":False,"candidates":[],"message":"Need more activity history to surface candidate patterns."}
    now=datetime.now(timezone.utc)
    by_label=defaultdict(list)
    for ts,l in rows: by_label[l].append(ts)
    candidates=[]
    for l,times in by_label.items():
        if len(times)<3: continue
        weekdays=Counter(t.weekday() for t in times)
        hours=Counter(t.hour for t in times)
        wd,wn=weekdays.most_common(1)[0]
        hr,hn=hours.most_common(1)[0]
        wd_dom=wn/len(times); hr_dom=hn/len(times)
        last=max(times); age=(now-last).total_seconds()/86400
        recency=math.exp(-min(age,30)/14)
        conf=_confidence(len(times),max(wd_dom,hr_dom),recency)
        if max(wd_dom,hr_dom)>=.45:
            candidates.append({"label":l,"observations":len(times),"common_weekday":wd,"common_hour":hr,"weekday_dominance":round(wd_dom,2),"hour_dominance":round(hr_dom,2),"last_seen":last.isoformat(),"confidence":conf,"status":"candidate" if conf<.70 else "strong candidate"})
    candidates.sort(key=lambda x:(x["confidence"],x["observations"]),reverse=True)
    return {"available":bool(candidates),"candidates":candidates[:30],"method":"repetition + weekday/hour concentration + recency"}


def daily_forecast(events, days=7):
    rows=activity_rows(events)
    if len(rows)<20:
        return {"available":False,"forecast":[],"message":"Need more history for daily forecasts."}
    by_day=defaultdict(Counter)
    for ts,l in rows: by_day[ts.weekday()][l]+=1
    out=[]
    now=datetime.now(timezone.utc)
    for i in range(1,days+1):
        t=now+timedelta(days=i)
        c=by_day.get(t.weekday(),Counter())
        if not c: continue
        label,n=c.most_common(1)[0]; total=sum(c.values())
        out.append({"date":t.date().isoformat(),"weekday":t.weekday(),"expected":label,"support":n,"observations":total,"confidence":round(min(.92,.30+.60*n/max(total,1)),2)})
    return {"available":bool(out),"forecast":out,"method":"historical weekday activity distribution"}
