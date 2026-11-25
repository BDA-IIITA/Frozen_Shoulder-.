from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logger import get_logger
from app.database.init_db import init_db
from app.api.routes import router as api_router
from app.api.websocket import ws_router
from app.services.sensor.ingestion import sensor_ingestion_service

logger = get_logger("Main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables and seed defaults
    logger.info("Initializing ShoulderSense database and default records...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    sensor_ingestion_service.stop_monitoring()
    sensor_ingestion_service.active_session_id = None
    # Shutdown
    logger.info("ShoulderSense backend shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Smart Frozen Shoulder Monitoring & Rehabilitation System — Backend API",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router)

@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "docs_url": "/docs",
        "api_v1": "/api"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
