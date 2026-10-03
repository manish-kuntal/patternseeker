from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Event
from ..services.intelligence import behavior_graph, focus_analysis, predictions, anomalies
from datetime import datetime, timedelta, timezone

router=APIRouter(prefix="/intelligence", tags=["intelligence"])

def load(db, days=30):
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(days,365)))
    return db.query(Event).filter(Event.timestamp>=cutoff).order_by(Event.timestamp.asc()).all()

@router.get("/behavior-graph")
def graph(days:int=30, db:Session=Depends(get_db)):
    return behavior_graph(load(db,days))

@router.get("/focus")
def focus(days:int=14, db:Session=Depends(get_db)):
    return focus_analysis(load(db,days))

@router.get("/predictions")
def predict(days:int=30, db:Session=Depends(get_db)):
    return predictions(load(db,days))

@router.get("/anomalies")
def anomaly(days:int=30, db:Session=Depends(get_db)):
    return anomalies(load(db,days),days)
