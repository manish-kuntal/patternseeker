from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class DeviceIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=50)

class EventIn(BaseModel):
    device_id: str
    event_type: str
    source: str
    timestamp: datetime
    project: Optional[str] = None
    application: Optional[str] = None
    duration_seconds: Optional[float] = None
    metadata: dict[str, Any] = {}

class EventBatch(BaseModel):
    events: list[EventIn]

class PatternOut(BaseModel):
    id: int
    pattern_type: str
    title: str
    description: str
    confidence: float
    evidence: dict
    ai_explanation: str | None = None
    created_at: datetime
