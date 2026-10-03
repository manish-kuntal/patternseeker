from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Device
from ..schemas import DeviceIn

router = APIRouter(prefix="/devices", tags=["devices"])

@router.post("")
def register_device(payload: DeviceIn, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == payload.device_id).first()
    now = datetime.now(timezone.utc)

    if device:
        device.name = payload.name
        device.platform = payload.platform
        device.last_seen = now
        device.active = True
    else:
        device = Device(
            device_id=payload.device_id,
            name=payload.name,
            platform=payload.platform,
            last_seen=now,
            active=True,
        )
        db.add(device)

    db.commit()
    return {"ok": True, "device_id": payload.device_id}

@router.get("")
def list_devices(db: Session = Depends(get_db)):
    rows = db.query(Device).order_by(Device.last_seen.desc()).all()
    return [{
        "device_id": x.device_id,
        "name": x.name,
        "platform": x.platform,
        "last_seen": x.last_seen,
        "active": x.active,
    } for x in rows]
