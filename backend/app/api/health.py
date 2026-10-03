from fastapi import APIRouter
from sqlalchemy import text
from ..db import engine

router = APIRouter()

@router.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "service": "pattern-api", "version": "1.0.0"}
