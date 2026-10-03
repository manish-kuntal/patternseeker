from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from ..db import get_db
from ..models import Event, Pattern
from ..services.prediction_engine import forecast, pattern_candidates, daily_forecast

router=APIRouter(prefix="/prediction", tags=["prediction-engine"])

def load(db, days=90):
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(days,365)))
    return db.query(Event).filter(Event.timestamp>=cutoff).order_by(Event.timestamp.asc()).all()

@router.get("/forecast")
def forecast_activity(hours:int=24, days:int=90, db:Session=Depends(get_db)):
    return forecast(load(db,days), max(1,min(hours,168)))

@router.get("/pattern-candidates")
def candidates(days:int=90, db:Session=Depends(get_db)):
    return pattern_candidates(load(db,days))

@router.get("/daily")
def daily(days:int=7, history_days:int=90, db:Session=Depends(get_db)):
    return daily_forecast(load(db,history_days), max(1,min(days,14)))

@router.get("/pattern-forecast")
def pattern_forecast(days:int=90, db:Session=Depends(get_db)):
    events=load(db,days)
    candidates=pattern_candidates(events)
    existing=db.query(Pattern).order_by(Pattern.confidence.desc()).limit(50).all()
    recurring=[{"id":p.id,"type":p.pattern_type,"title":p.title,"confidence":p.confidence,"description":p.description} for p in existing if p.confidence>=0.60]
    return {"candidates":candidates.get("candidates",[]),"established":recurring,"note":"Forecasts are evidence-based recurrence estimates, not guarantees."}
