import uuid

import httpx
from fastmcp import Client

from tests.conftest import MakeUser, make_token


async def test_rejects_missing_and_invalid_tokens(server_url: str) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"Accept": "application/json, text/event-stream"}
    uid = uuid.uuid4()
    async with httpx.AsyncClient(base_url=server_url) as http:
        assert (await http.post("/mcp", json=body, headers=headers)).status_code == 401
        for token in (
            make_token(uid, secret="zly-sekret-tez-ma-32-bajty-dlugosci"),
            make_token(uid, iss="x"),
        ):
            auth = {"Authorization": f"Bearer {token}"}
            r = await http.post("/mcp", json=body, headers=headers | auth)
            assert r.status_code == 401
        assert (await http.get("/health")).json() == {"status": "ok"}


async def test_valid_token_reaches_tools(server_url: str, make_user: MakeUser) -> None:
    user = await make_user()
    await user.add("42.00", "Jedzenie", "2026-11-05")
    async with Client(f"{server_url}/mcp", auth=make_token(user.id)) as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            "get_summary", {"date_from": "2026-11-01", "date_to": "2026-11-30"}
        )
    assert len(tools) == 9
    assert result.structured_content is not None
    assert result.structured_content["expense"] == "42.00"
