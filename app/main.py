import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.events import router as events_router
from app.api.routes.github_webhooks import router as github_webhooks_router
from app.api.routes.health import router as health_router
from app.api.routes.jira_webhooks import router as jira_webhooks_router
from app.api.routes.metrics import router as metrics_router
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.base import Base
from app.db.database import get_engine

logger = get_logger("github_webhooks")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    Base.metadata.create_all(bind=get_engine())
    yield


app = FastAPI(title="GitHub Webhook Testing Service", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(github_webhooks_router)
app.include_router(jira_webhooks_router)
app.include_router(events_router)
app.include_router(metrics_router)
