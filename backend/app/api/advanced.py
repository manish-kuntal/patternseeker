from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from ..db import get_db
from ..models import Event
from ..services.advanced import daily_brief, routines, project_lifecycle, context_switches, data_quality, search_events
router=APIRouter(prefix="/advanced", tags=["advanced-intelligence"])
def load(db, days=30):
    cutoff=datetime.now(timezone.utc)-timedelta(days=max(1,min(days,365)))
    return db.query(Event).filter(Event.timestamp>=cutoff).order_by(Event.timestamp.asc()).all()
@router.get('/daily-brief')
def brief(days:int=1, db:Session=Depends(get_db)): return daily_brief(load(db,max(1,days)),days)
@router.get('/routines')
def routine(days:int=30, db:Session=Depends(get_db)): return routines(load(db,days),days)
@router.get('/project-lifecycle')
def lifecycle(days:int=180, db:Session=Depends(get_db)): return project_lifecycle(load(db,days),days)
@router.get('/context-switches')
def switches(days:int=14, db:Session=Depends(get_db)): return context_switches(load(db,days))
@router.get('/data-quality')
def quality(days:int=7, db:Session=Depends(get_db)): return data_quality(load(db,days),days)
@router.get('/search')
def search(q:str=Query(min_length=1,max_length=100), limit:int=50, db:Session=Depends(get_db)): return {'query':q,'results':search_events(load(db,365),q,min(max(limit,1),100))}
