from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.admin_sessions import router as admin_sessions_router
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.api.stories import router as stories_router
from app.storage.engine import init_db


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Accept-All Narrative RPG API", lifespan=lifespan)
app.include_router(health_router)
app.include_router(stories_router)
app.include_router(sessions_router)
app.include_router(admin_sessions_router)
