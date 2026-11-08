import asyncio
import socket
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import jwt
import pytest
import uvicorn
from app.config import Settings
from fastmcp import Client

from finance_tools.server import create_server
from tests.conftest import MakeUser

SECRET = "mcp-test-secret-at-least-32-bytes!!"
ISSUER = "http://127.0.0.1:54321/auth/v1"


def _token(user_id: uuid.UUID, secret: str = SECRET, iss: str = ISSUER) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "aud": "authenticated",
        "iss": iss,
        "role": "authenticated",
        "iat": now,
        "exp": now + 600,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture(scope="module")
async def server_url(database: None) -> AsyncIterator[str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    app = create_server(Settings(supabase_jwt_secret=SECRET)).http_app()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.02)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    await task


async def test_rejects_missing_and_invalid_tokens(server_url: str) -> None:
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    headers = {"Accept": "application/json, text/event-stream"}
    uid = uuid.uuid4()
    async with httpx.AsyncClient(base_url=server_url) as http:
        assert (await http.post("/mcp", json=body, headers=headers)).status_code == 401
        for token in (
            _token(uid, secret="zly-sekret-tez-ma-32-bajty-dlugosci"),
            _token(uid, iss="x"),
        ):
            auth = {"Authorization": f"Bearer {token}"}
            r = await http.post("/mcp", json=body, headers=headers | auth)
            assert r.status_code == 401
        assert (await http.get("/health")).json() == {"status": "ok"}


async def test_valid_token_reaches_tools(server_url: str, make_user: MakeUser) -> None:
    user = await make_user()
    await user.add("42.00", "Jedzenie", "2026-11-05")
    async with Client(f"{server_url}/mcp", auth=_token(user.id)) as client:
        tools = await client.list_tools()
        result = await client.call_tool(
            "get_summary", {"date_from": "2026-11-01", "date_to": "2026-11-30"}
        )
    assert len(tools) == 9
    assert result.structured_content is not None
    assert result.structured_content["expense"] == "42.00"
