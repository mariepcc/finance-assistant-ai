import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient

from app.agent.orchestrator import Orchestrator
from app.agent.router import RouteDecision
from app.api.chat import NO_API_KEY, AgentFactory, get_agent_factory
from app.config import Settings
from tests.conftest import AuthHeaders, Onboarded
from tests.fakes import FakeGateway, FakeLLM, text_step, tool_step


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for frame in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in frame.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def fake_factory(llm: FakeLLM, tokens: list[str]) -> AgentFactory:
    @asynccontextmanager
    async def factory(token: str) -> AsyncIterator[Orchestrator]:
        tokens.append(token)
        yield Orchestrator(llm, FakeGateway(), Settings(anthropic_api_key=None))

    return factory


async def test_chat_requires_token(client: AsyncClient) -> None:
    r = await client.post("/chat", json={"message": "hej"})
    assert r.status_code == 401


async def test_chat_requires_consent(client: AsyncClient, auth: AuthHeaders) -> None:
    r = await client.post("/chat", json={"message": "hej"}, headers=auth(uuid.uuid4()))
    assert r.status_code == 403


async def test_chat_validates_message(client: AsyncClient, onboarded: Onboarded) -> None:
    headers, _ = await onboarded()
    r = await client.post("/chat", json={"message": ""}, headers=headers)
    assert r.status_code == 422


async def test_chat_without_api_key_streams_error(
    client: AsyncClient, onboarded: Onboarded
) -> None:
    headers, _ = await onboarded()
    r = await client.post("/chat", json={"message": "hej"}, headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(r.text) == [("error", {"message": NO_API_KEY})]


async def test_chat_streams_agent_events(
    app: FastAPI, client: AsyncClient, onboarded: Onboarded
) -> None:
    headers, _ = await onboarded()
    llm = FakeLLM(
        routes=[RouteDecision.model_validate({"categories": ["analysis"]})],
        steps={
            "analysis": [
                tool_step(("get_summary", {"date_from": "2026-10-01", "date_to": "2026-10-31"})),
                text_step("W październiku wydałaś 7937,79 zł."),
            ]
        },
    )
    tokens: list[str] = []
    app.dependency_overrides[get_agent_factory] = lambda: fake_factory(llm, tokens)
    history = [{"role": "user", "content": f"pytanie {i}"} for i in range(10)]
    r = await client.post(
        "/chat",
        json={"message": "Ile wydałam?", "history": history, "previous_categories": ["analysis"]},
        headers=headers,
    )
    assert r.status_code == 200
    events = parse_sse(r.text)
    kinds = [k for k, _ in events]
    assert kinds[0] == "status"
    assert kinds[-1] == "done"
    assert "".join(d["text"] for k, d in events if k == "token") == (
        "W październiku wydałaś 7937,79 zł."
    )
    assert events[-1][1]["verified"] is True
    assert tokens == [headers["Authorization"].removeprefix("Bearer ")]
    prompt = llm.parse_calls[0]
    assert "pytanie 3" not in prompt
    assert "pytanie 4" in prompt
    assert "pytanie 9" in prompt
