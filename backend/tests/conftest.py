import asyncio
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import jwt
import pytest
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from app.config import Settings, get_settings
from app.db import get_session
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/finance_test"
)
JWT_SECRET = "test-secret-at-least-32-bytes-long!!"
TABLES = "transactions, budgets, proposals, categories, profiles"


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    target = make_url(TEST_DATABASE_URL)
    name = target.database

    async def recreate() -> None:
        admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{name}"'))
        await admin.dispose()

    asyncio.run(recreate())
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield TEST_DATABASE_URL


@pytest.fixture(scope="session")
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session_factory(engine: AsyncEngine) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES} CASCADE"))


@pytest.fixture
def app(session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    application = create_app()

    async def _session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as s:
            yield s

    application.dependency_overrides[get_settings] = lambda: Settings(
        supabase_jwt_secret=JWT_SECRET, anthropic_api_key=None
    )
    application.dependency_overrides[get_session] = _session
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def make_token(
    user_id: uuid.UUID,
    *,
    secret: str = JWT_SECRET,
    aud: str = "authenticated",
    iss: str = "http://127.0.0.1:54321/auth/v1",
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(user_id),
            "aud": aud,
            "iss": iss,
            "role": "authenticated",
            "iat": now,
            "exp": now + 3600,
        },
        secret,
        algorithm="HS256",
    )


AuthHeaders = Callable[[uuid.UUID], dict[str, str]]
Onboarded = Callable[[], Awaitable[tuple[dict[str, str], dict[str, str]]]]


@pytest.fixture
def auth() -> AuthHeaders:
    return lambda user_id: {"Authorization": f"Bearer {make_token(user_id)}"}


@pytest.fixture
async def onboarded(client: AsyncClient, auth: AuthHeaders) -> Onboarded:

    async def _make() -> tuple[dict[str, str], dict[str, str]]:
        headers = auth(uuid.uuid4())
        r = await client.post("/me/consent", json={"accepted": True}, headers=headers)
        assert r.status_code == 200, r.text
        cats = (await client.get("/categories", headers=headers)).json()
        return headers, {c["name"]: c["id"] for c in cats}

    return _make


UserCtx = tuple[uuid.UUID, dict[str, str], dict[str, str]]
MakeUser = Callable[[], Awaitable[UserCtx]]


@pytest.fixture
async def make_user(client: AsyncClient, auth: AuthHeaders) -> MakeUser:
    async def _make() -> UserCtx:
        uid = uuid.uuid4()
        headers = auth(uid)
        r = await client.post("/me/consent", json={"accepted": True}, headers=headers)
        assert r.status_code == 200, r.text
        cats = (await client.get("/categories", headers=headers)).json()
        return uid, headers, {c["name"]: c["id"] for c in cats}

    return _make
