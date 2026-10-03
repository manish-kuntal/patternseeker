import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Pattern
from ..services.ollama import explain

router = APIRouter(prefix="/insights", tags=["insights"])

@router.get("")
async def insights(db: Session = Depends(get_db)):
    rows = db.query(Pattern).order_by(Pattern.created_at.desc()).limit(50).all()
    result = []

    for p in rows:
        evidence = json.loads(p.evidence_json)

        if not p.ai_explanation:
            ai = await explain(p.title, p.description, evidence)
            if ai:
                p.ai_explanation = ai

        result.append({
            "id": p.id,
            "pattern_type": p.pattern_type,
            "title": p.title,
            "description": p.description,
            "confidence": p.confidence,
            "evidence": evidence,
            "ai_explanation": p.ai_explanation,
            "created_at": p.created_at,
        })

    db.commit()
    return result
