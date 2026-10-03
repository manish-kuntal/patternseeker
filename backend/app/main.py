from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db import init_db
from .api import health, devices, events, analytics, insights, projects, intelligence, advanced, prediction

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="PatternSeeker API",
    version="1.0.0",
    description="PatternSeeker Personal Behavior Intelligence Engine",
    lifespan=lifespan,
)

origins = [x.strip() for x in settings.cors_origins.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(devices.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(advanced.router, prefix="/api")
app.include_router(prediction.router, prefix="/api")
