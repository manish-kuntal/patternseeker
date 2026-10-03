import hashlib
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, Device
from ..schemas import EventBatch, EventIn
from ..security import require_ingest_key

router = APIRouter(prefix="/events", tags=["events"])

def normalize_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()

def fingerprint(payload: EventIn) -> str:
    raw = json.dumps({
        "device_id": payload.device_id,
        "event_type": payload.event_type,
        "source": payload.source,
        "timestamp": normalize_timestamp(payload.timestamp),
        "project": payload.project,
        "application": payload.application,
        "metadata": payload.metadata,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def save_event(payload: EventIn, db: Session):
    fp = fingerprint(payload)

    existing = db.query(Event).filter(Event.fingerprint == fp).first()
    if existing:
        return False

    timestamp = payload.timestamp
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    event = Event(
        fingerprint=fp,
        device_id=payload.device_id,
        event_type=payload.event_type,
        source=payload.source,
        timestamp=timestamp,
        project=payload.project,
        application=payload.application,
        duration_seconds=payload.duration_seconds,
        metadata_json=json.dumps(payload.metadata, ensure_ascii=False),
    )
    db.add(event)

    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    if device:
        device.last_seen = datetime.now(timezone.utc)

    return True

@router.post("", dependencies=[Depends(require_ingest_key)])
def ingest_event(payload: EventIn, db: Session = Depends(get_db)):
    accepted = save_event(payload, db)
    db.commit()
    return {"ok": True, "accepted": accepted}

@router.post("/batch", dependencies=[Depends(require_ingest_key)])
def ingest_batch(payload: EventBatch, db: Session = Depends(get_db)):
    accepted = 0
    for item in payload.events:
        if save_event(item, db):
            accepted += 1
    db.commit()
    return {"ok": True, "accepted": accepted, "received": len(payload.events)}

@router.get("/recent")
def recent_events(limit: int = 50, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 500))
    rows = db.query(Event).order_by(Event.timestamp.desc()).limit(limit).all()

    return [{
        "id": x.id,
        "device_id": x.device_id,
        "event_type": x.event_type,
        "source": x.source,
        "timestamp": x.timestamp,
        "project": x.project,
        "application": x.application,
        "duration_seconds": x.duration_seconds,
    } for x in rows]
