from datetime import datetime, timedelta, timezone
from collections import Counter
import statistics
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, Pattern
from ..services.pattern_engine import detect_patterns, _app_sessions

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _aware(ts):
    return ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts


@router.post("/detect")
def detect(db: Session = Depends(get_db)):
    patterns = detect_patterns(db)
    return {"ok": True, "new_patterns": len(patterns)}


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    return {
        "events": db.query(func.count(Event.id)).scalar() or 0,
        "projects": db.query(func.count(func.distinct(Event.project))).filter(Event.project.isnot(None)).scalar() or 0,
        "git_commits": db.query(func.count(Event.id)).filter(Event.event_type == "git_commit").scalar() or 0,
        "android_events": db.query(func.count(Event.id)).filter(Event.source == "android").scalar() or 0,
        "devices": db.query(func.count(func.distinct(Event.device_id))).scalar() or 0,
        "patterns": db.query(func.count(Pattern.id)).scalar() or 0,
    }


@router.get("/timeline")
def timeline(days: int = 30, db: Session = Depends(get_db)):
    days = max(1, min(days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(Event).filter(Event.timestamp >= cutoff).order_by(Event.timestamp.asc()).all()
    data = {}
    for e in rows:
        key = _aware(e.timestamp).date().isoformat()
        data[key] = data.get(key, 0) + 1
    return [{"date": k, "events": v} for k, v in sorted(data.items())]


@router.get("/app-usage")
def app_usage(days: int = 1, db: Session = Depends(get_db)):
    days = max(1, min(days, 30))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(Event).filter(
        Event.event_type == "application_usage",
        Event.application.isnot(None),
        Event.timestamp >= cutoff,
    ).order_by(Event.timestamp.asc()).all()

    totals = Counter()
    counts = Counter()
    for row in rows:
        totals[row.application] += float(row.duration_seconds or 0)
        counts[row.application] += 1

    total_seconds = sum(totals.values())
    items = [{
        "application": app,
        "seconds": round(seconds, 1),
        "minutes": round(seconds / 60, 1),
        "hours": round(seconds / 3600, 2),
        "samples": counts[app],
        "share": round(seconds / total_seconds, 3) if total_seconds else 0,
    } for app, seconds in totals.most_common(30)]

    return {"days": days, "total_seconds": round(total_seconds, 1), "total_minutes": round(total_seconds / 60, 1), "applications": items}


@router.get("/intelligence")
def intelligence(days: int = 30, db: Session = Depends(get_db)):
    """Compact feature set used by the dashboard and future AI layer."""
    days = max(1, min(days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = db.query(Event).filter(Event.timestamp >= cutoff).order_by(Event.timestamp.asc()).all()

    app_events = [e for e in events if e.event_type == "application_usage" and e.application]
    sessions = _app_sessions(app_events)
    project_events = [e for e in events if e.project]
    app_seconds = Counter()
    for e in app_events:
        app_seconds[e.application] += float(e.duration_seconds or 0)

    project_counts = Counter(e.project for e in project_events)
    hour_counts = Counter(_aware(e.timestamp).hour for e in events)
    transitions = Counter()
    for a, b in zip(app_events, app_events[1:]):
        if a.application != b.application and _aware(b.timestamp) - _aware(a.timestamp) <= timedelta(minutes=15):
            transitions[(a.application, b.application)] += 1

    active_days = len({_aware(e.timestamp).date() for e in events})
    total_app_seconds = sum(app_seconds.values())
    median_session = statistics.median([s["seconds"] for s in sessions]) if sessions else 0
    top_project, top_project_count = project_counts.most_common(1)[0] if project_counts else (None, 0)
    top_app, top_app_seconds = app_seconds.most_common(1)[0] if app_seconds else (None, 0)
    peak_hour, peak_count = hour_counts.most_common(1)[0] if hour_counts else (None, 0)
    top_transition, transition_count = transitions.most_common(1)[0] if transitions else (None, 0)

    return {
        "window_days": days,
        "events": len(events),
        "active_days": active_days,
        "application_sessions": len(sessions),
        "median_session_minutes": round(median_session / 60, 1),
        "total_app_minutes": round(total_app_seconds / 60, 1),
        "top_application": {"name": top_app, "minutes": round(top_app_seconds / 60, 1)} if top_app else None,
        "top_project": {"name": top_project, "signals": top_project_count} if top_project else None,
        "peak_hour": {"hour": peak_hour, "signals": peak_count} if peak_hour is not None else None,
        "top_transition": {"from": top_transition[0], "to": top_transition[1], "occurrences": transition_count} if top_transition else None,
    }

@router.get("/system")
def system_metrics(db: Session = Depends(get_db)):
    """Return the most recent hardware telemetry sample."""
    import json

    row = db.query(Event).filter(Event.event_type == "system_metrics").order_by(Event.timestamp.desc()).first()
    if not row:
        return {"available": False, "metrics": None, "timestamp": None}
    try:
        metrics = json.loads(row.metadata_json or "{}")
    except Exception:
        metrics = {}
    return {"available": True, "timestamp": row.timestamp, "device_id": row.device_id, "metrics": metrics}


@router.get("/health-intelligence")
def health_intelligence(db: Session = Depends(get_db)):
    """Hardware + collector health summary with safe handling of unavailable sensors."""
    import json
    row = db.query(Event).filter(Event.event_type == "system_metrics").order_by(Event.timestamp.desc()).first()
    if not row:
        return {"available": False}
    try:
        m = json.loads(row.metadata_json or "{}")
    except Exception:
        m = {}
    cpu = m.get("cpu", {}); mem = m.get("memory", {}); gpu = m.get("gpu", {}); proc = m.get("process", {})
    cpu_load = float(cpu.get("usage_percent") or 0)
    mem_load = float(mem.get("usage_percent") or 0)
    gpu_temp = gpu.get("temperature_c")
    warnings = []
    if mem_load >= 90: warnings.append("memory_pressure")
    if cpu_load >= 90: warnings.append("high_cpu_load")
    if gpu_temp is not None and float(gpu_temp) >= 85: warnings.append("high_gpu_temperature")
    if gpu.get("power_status") == "invalid_driver_value": warnings.append("gpu_power_unreliable")
    impact = {"cpu_percent": proc.get("cpu_percent"), "memory_mb": proc.get("memory_mb"), "threads": proc.get("threads")}
    return {
        "available": True, "timestamp": row.timestamp, "warnings": warnings,
        "collector_impact": impact,
        "health": "attention" if warnings else "healthy",
        "gpu_power_reliable": gpu.get("power_status") == "valid",
    }


@router.get("/telemetry-history")
def telemetry_history(hours: int = 6, db: Session = Depends(get_db)):
    """Compact hardware history for charts. Raw event metadata stays local."""
    import json
    hours = max(1, min(hours, 168))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (db.query(Event)
            .filter(Event.event_type == "system_metrics", Event.timestamp >= cutoff)
            .order_by(Event.timestamp.asc()).all())
    points = []
    for row in rows:
        try:
            m = json.loads(row.metadata_json or "{}")
        except Exception:
            continue
        cpu=m.get("cpu",{}); mem=m.get("memory",{}); gpu=m.get("gpu",{}); disk=m.get("disk",{}); net=m.get("network",{})
        points.append({
            "timestamp": _aware(row.timestamp).isoformat(),
            "cpu": cpu.get("usage_percent"),
            "clock_mhz": cpu.get("clock_mhz"),
            "memory": mem.get("usage_percent"),
            "gpu": gpu.get("utilization_percent"),
            "gpu_temp": gpu.get("temperature_c"),
            "disk_read_mb_s": disk.get("read_mb_s"),
            "disk_write_mb_s": disk.get("write_mb_s"),
            "upload_mb_s": net.get("upload_mb_s"),
            "download_mb_s": net.get("download_mb_s"),
        })
    return {"hours": hours, "points": points[-720:]}


@router.get("/performance")
def performance(db: Session = Depends(get_db)):
    """Current runtime/performance state with a simple deterministic health score."""
    import json
    row = db.query(Event).filter(Event.event_type == "system_metrics").order_by(Event.timestamp.desc()).first()
    if not row:
        return {"available": False}
    try:
        m=json.loads(row.metadata_json or "{}")
    except Exception:
        m={}
    cpu=m.get("cpu",{}); mem=m.get("memory",{}); gpu=m.get("gpu",{}); disk=m.get("disk",{}); proc=m.get("process",{})
    score=100
    deductions=[]
    cpu_load=float(cpu.get("usage_percent") or 0)
    mem_load=float(mem.get("usage_percent") or 0)
    gpu_temp=gpu.get("temperature_c")
    disk_load=float(disk.get("usage_percent") or 0)
    if cpu_load>85: score-=20; deductions.append("high_cpu")
    elif cpu_load>70: score-=8; deductions.append("elevated_cpu")
    if mem_load>90: score-=25; deductions.append("memory_pressure")
    elif mem_load>80: score-=10; deductions.append("high_memory")
    if disk_load>90: score-=15; deductions.append("low_storage")
    if gpu_temp is not None:
        if float(gpu_temp)>=90: score-=25; deductions.append("gpu_temperature")
        elif float(gpu_temp)>=80: score-=10; deductions.append("gpu_warm")
    collector_cpu=float(proc.get("cpu_percent") or 0)
    collector_mem=float(proc.get("memory_mb") or 0)
    if collector_cpu>5: score-=8; deductions.append("collector_cpu_impact")
    if collector_mem>500: score-=5; deductions.append("collector_memory_impact")
    return {
        "available": True,
        "timestamp": row.timestamp,
        "score": max(0, min(100, score)),
        "state": "excellent" if score>=90 else "healthy" if score>=75 else "attention" if score>=55 else "critical",
        "factors": deductions,
        "collector": {"cpu_percent": proc.get("cpu_percent"), "memory_mb": proc.get("memory_mb"), "threads": proc.get("threads")},
        "top_processes": m.get("top_processes", []),
    }


@router.get("/screen-intelligence")
def screen_intelligence(limit: int = 30, db: Session = Depends(get_db)):
    """Return structured screen-context observations only; no screenshots/raw OCR."""
    import json
    limit = max(1, min(limit, 200))
    rows = (db.query(Event)
            .filter(Event.event_type == "screen_context")
            .order_by(Event.timestamp.desc())
            .limit(limit).all())
    items = []
    for row in rows:
        try:
            m = json.loads(row.metadata_json or "{}")
        except Exception:
            m = {}
        items.append({
            "timestamp": row.timestamp,
            "application": row.application,
            "category": m.get("category", "unknown"),
            "confidence": m.get("confidence", 0),
            "signals": m.get("signals", []),
            "vision_summary": m.get("vision_summary"),
            "privacy": m.get("privacy", {"screenshot_stored": False, "raw_ocr_stored": False, "cloud_upload": False}),
        })
    categories = Counter(x["category"] for x in items if x["category"] not in {"unknown", "unchanged", "protected"})
    return {"enabled": bool(items), "observations": items, "top_categories": [{"category": k, "observations": v} for k, v in categories.most_common(10)]}
