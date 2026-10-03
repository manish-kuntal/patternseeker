from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean, UniqueConstraint, Index
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(120), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    platform = Column(String(50), nullable=False)
    last_seen = Column(DateTime(timezone=True), default=utcnow)
    active = Column(Boolean, default=True)

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    fingerprint = Column(String(64), nullable=False, unique=True, index=True)
    device_id = Column(String(120), nullable=False, index=True)
    event_type = Column(String(80), nullable=False, index=True)
    source = Column(String(80), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    project = Column(String(255), nullable=True, index=True)
    application = Column(String(255), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    metadata_json = Column(Text, nullable=True)

Index("ix_events_project_time", Event.project, Event.timestamp)

class Pattern(Base):
    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True)
    fingerprint = Column(String(64), nullable=False, unique=True, index=True)
    pattern_type = Column(String(80), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    evidence_json = Column(Text, nullable=False)
    ai_explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
