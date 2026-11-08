import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.models import Budget, Category, Transaction, TransactionType
from app.repositories import profiles as profiles_repo
from app.services import onboarding
from fastmcp import Client, FastMCP
from fastmcp.server.auth import AccessToken
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from sqlalchemy import make_url, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from finance_tools.server import create_server

TEST_DATABASE_URL = os.environ.get(
    "MCP_TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/finance_mcp_test",
)
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
TABLES = "transactions, budgets, proposals, categories, profiles"


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    target = make_url(TEST_DATABASE_URL)

    async def recreate() -> None:
        admin = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{target.database}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
        await admin.dispose()

    asyncio.run(recreate())
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ.pop("SUPABASE_JWT_SECRET", None)
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    async with get_sessionmaker()() as s:
        await s.execute(text(f"TRUNCATE {TABLES} CASCADE"))
        await s.commit()


@pytest.fixture(scope="session")
def mcp(database: None) -> FastMCP:
    return create_server()


class UserData:
    def __init__(self, user_id: uuid.UUID, categories: dict[str, uuid.UUID]) -> None:
        self.id = user_id
        self.categories = categories

    async def add(
        self,
        amount: str,
        category: str,
        day: str,
        type: TransactionType = TransactionType.EXPENSE,
        note: str | None = None,
    ) -> None:
        async with get_sessionmaker()() as s:
            s.add(
                Transaction(
                    user_id=self.id,
                    type=type,
                    amount=Decimal(amount),
                    currency="PLN",
                    category_id=self.categories[category],
                    occurred_on=date.fromisoformat(day),
                    note=note,
                )
            )
            await s.commit()

    async def budget(self, category: str, amount: str) -> None:
        async with get_sessionmaker()() as s:
            s.add(
                Budget(
                    user_id=self.id,
                    category_id=self.categories[category],
                    amount=Decimal(amount),
                )
            )
            await s.commit()


MakeUser = Callable[[], Awaitable[UserData]]


@pytest.fixture
def make_user() -> MakeUser:
    async def _make() -> UserData:
        async with get_sessionmaker()() as s:
            profile = await profiles_repo.get_or_create(s, uuid.uuid4())
            await onboarding.accept_consent(s, profile, "PLN")
            await s.commit()
            cats = (await s.scalars(select(Category).where(Category.user_id == profile.id))).all()
            return UserData(profile.id, {c.name: c.id for c in cats})

    return _make


ClientAs = Callable[[uuid.UUID | None], AbstractAsyncContextManager[Client[Any]]]


@pytest.fixture
def client_as(mcp: FastMCP) -> ClientAs:
    @asynccontextmanager
    async def _client(user_id: uuid.UUID | None) -> AsyncIterator[Client[Any]]:
        user = None
        if user_id is not None:
            token = AccessToken(
                token="test", client_id="test", scopes=[], claims={"sub": str(user_id)}
            )
            user = AuthenticatedUser(token)
        reset = auth_context_var.set(user)
        try:
            async with Client(mcp) as client:
                yield client
        finally:
            auth_context_var.reset(reset)

    return _client


async def call(client: Client[Any], tool: str, **args: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    assert result.structured_content is not None
    return result.structured_content
