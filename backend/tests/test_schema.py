from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base


async def test_migrations_match_models(engine: AsyncEngine) -> None:
    def diff(conn: Connection) -> list[Any]:
        return list(compare_metadata(MigrationContext.configure(conn), Base.metadata))

    async with engine.connect() as conn:
        assert await conn.run_sync(diff) == []


async def test_rls_enabled_on_all_tables(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT relname, relrowsecurity FROM pg_class "
                "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
                "AND relname <> 'alembic_version'"
            )
        )
        flags = {name: enabled for name, enabled in rows}
    assert set(flags) == set(Base.metadata.tables)
    assert all(flags.values()), flags
