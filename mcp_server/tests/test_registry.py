import json

import pytest
from fastmcp import FastMCP

from finance_tools.categories import TOOL_CATEGORIES
from finance_tools.server import TOOLS, ToolSpec, check_tool_categories
from tests.conftest import ClientAs


async def test_every_tool_has_exactly_its_category(mcp: FastMCP) -> None:
    tools = await mcp.list_tools()
    assert {t.name for t in tools} == set(TOOL_CATEGORIES)
    for t in tools:
        assert t.tags == {TOOL_CATEGORIES[t.name].value}, t.name


async def test_no_tool_accepts_user_id(mcp: FastMCP) -> None:
    for t in await mcp.list_tools():
        schema = json.dumps(t.parameters)
        assert "user_id" not in schema and "userId" not in schema, t.name


async def test_write_tools_are_only_proposals(mcp: FastMCP) -> None:
    for t in await mcp.list_tools():
        writes = not (t.annotations and t.annotations.read_only_hint)
        assert writes == t.name.startswith("propose_"), t.name
    assert "add_transaction" not in {t.name for t in await mcp.list_tools()}


def test_startup_check_detects_inconsistency() -> None:
    check_tool_categories(TOOLS)
    with pytest.raises(RuntimeError, match="niezarejestrowane"):
        check_tool_categories(TOOLS[1:])

    async def unknown_tool() -> None:
        return None

    with pytest.raises(RuntimeError, match="bez kategorii"):
        check_tool_categories([*TOOLS, ToolSpec(unknown_tool, "x")])


async def test_requires_identity(client_as: ClientAs) -> None:
    async with client_as(None) as c:
        result = await c.call_tool("list_categories", {}, raise_on_error=False)
    assert result.is_error
    assert "uwierzytelnionego" in str(result.content)
