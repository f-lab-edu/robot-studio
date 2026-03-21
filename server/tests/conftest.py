import os
import asyncio
import asyncpg

# app 모듈 import 전에 환경변수 설정
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("REDIS_URL", "redis://fake")

_BASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://robot_studio:robot_studio@postgres:5432/robot_studio",
)

_TEST_DB_NAME = "robot_studio_test"
TEST_DATABASE_URL = _BASE_URL.rsplit("/", 1)[0] + f"/{_TEST_DB_NAME}"
_ASYNCPG_ADMIN_URL = (
    _BASE_URL.replace("postgresql+asyncpg://", "postgresql://").rsplit("/", 1)[0]
    + "/postgres"
)


async def _ensure_test_db():
    """robot_studio_test DB가 없으면 생성"""
    conn = await asyncpg.connect(_ASYNCPG_ADMIN_URL)
    exists = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname=$1", _TEST_DB_NAME
    )
    if not exists:
        await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    await conn.close()


asyncio.run(_ensure_test_db())

os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest_asyncio
import fakeredis.aioredis
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

# database 모듈을 먼저 import한 뒤 엔진을 교체
# NullPool: 각 작업마다 독립적인 연결 사용 → fixture 간 연결 충돌 방지
import app.infra.database as db_module
from app.infra.database import Base

_test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
_test_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)

db_module.engine = _test_engine
db_module.async_session = _test_session_factory

# 엔진 교체 후 app import → main.py의 lifespan이 test 엔진 사용
from app.main import app
from app.infra.database import get_db
from app.core.redis import get_redis


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """각 테스트 전 테이블 생성, 후 제거"""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with _test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def fake_redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.aclose()


@pytest_asyncio.fixture
async def client(db_session, fake_redis):
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
