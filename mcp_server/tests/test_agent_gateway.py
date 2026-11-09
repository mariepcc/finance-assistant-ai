from app.agent.tools import connect
from app.agent.types import AgentError

from finance_tools.categories import TOOL_CATEGORIES
from tests.conftest import MakeUser, make_token


async def test_gateway_groups_tools_by_category(server_url: str, make_user: MakeUser) -> None:
    user = await make_user()
    async with connect(f"{server_url}/mcp", make_token(user.id)) as gateway:
        tools = await gateway.list_tools()
    assert {t.name: t.category for t in tools} == {n: c.value for n, c in TOOL_CATEGORIES.items()}
    for tool in tools:
        api = tool.to_api()
        assert api["input_schema"]["type"] == "object"
        assert "user_id" not in api["input_schema"].get("properties", {})
        assert tool.description


async def test_gateway_calls_tools_as_token_owner(server_url: str, make_user: MakeUser) -> None:
    alice = await make_user()
    bob = await make_user()
    await alice.add("42.00", "Jedzenie", "2026-11-05")
    args = {"date_from": "2026-11-01", "date_to": "2026-11-30"}

    async with connect(f"{server_url}/mcp", make_token(alice.id)) as gateway:
        own = await gateway.call("get_summary", args)
        bad = await gateway.call("search_transactions", {"category": "Bzdura"})
    async with connect(f"{server_url}/mcp", make_token(bob.id)) as gateway:
        other = await gateway.call("get_summary", args)

    assert not own.is_error
    assert own.data["expense"] == "42.00"
    assert other.data["expense"] == "0.00"
    assert bad.is_error
    assert "Bzdura" in bad.data["error"]


async def test_gateway_rejects_invalid_token(server_url: str) -> None:
    try:
        async with connect(f"{server_url}/mcp", "zly-token") as gateway:
            await gateway.list_tools()
    except AgentError as exc:
        assert "niedostępny" in exc.message
    else:
        raise AssertionError("oczekiwano AgentError")
