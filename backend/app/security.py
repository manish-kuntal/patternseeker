from fastapi import Header, HTTPException
from .core.config import settings

def require_ingest_key(x_pattern_key: str | None = Header(default=None)):
    if settings.environment == "development" and settings.ingest_api_key == "change-me":
        return
    if x_pattern_key != settings.ingest_api_key:
        raise HTTPException(status_code=401, detail="Invalid PATTERN ingest key")
