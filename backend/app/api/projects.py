from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models import Event

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("")
def projects(days: int = 90, db: Session = Depends(get_db)):
    days = max(1, min(days, 365))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.query(Event).filter(Event.timestamp >= cutoff, Event.project.isnot(None)).all()
    grouped = defaultdict(list)
    for e in rows:
        grouped[e.project].append(e)

    result = []
    for name, events in grouped.items():
        timestamps = sorted(e.timestamp for e in events)
        active_days = len({(t.date() if hasattr(t, 'date') else t) for t in timestamps})
        commits = sum(1 for e in events if e.event_type == "git_commit")
        file_activity = sum(1 for e in events if e.event_type in {"project_activity", "file_activity"})
        first_seen = timestamps[0].isoformat() if timestamps else None
        last_seen = timestamps[-1].isoformat() if timestamps else None
        result.append({
            "project": name,
            "events": len(events),
            "active_days": active_days,
            "git_commits": commits,
            "file_activity": file_activity,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "status": "active" if last_seen and (datetime.now(timezone.utc) - timestamps[-1].replace(tzinfo=timezone.utc) if timestamps[-1].tzinfo is None else datetime.now(timezone.utc) - timestamps[-1]) <= timedelta(days=2) else "inactive",
        })
    result.sort(key=lambda x: (x["events"], x["last_seen"] or ""), reverse=True)
    return {"days": days, "projects": result}
