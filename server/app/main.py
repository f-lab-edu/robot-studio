from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import objects, auth, datasets

from app.infra.database import engine, Base
from app.models.user import User, UserToken, ApiCredential  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Robot Studio API", lifespan=lifespan)

app.include_router(objects.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}