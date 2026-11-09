import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.llm import AnthropicLLM
from app.agent.orchestrator import ChatInput, Orchestrator
from app.agent.tools import connect
from app.agent.types import AgentError, ChatTurn, Event
from app.api.deps import SessionDep
from app.auth import CurrentUserDep
from app.config import Settings, get_settings
from app.errors import ConsentRequiredError
from app.repositories import profiles as profiles_repo
from app.schemas.chat import ChatRequest

router = APIRouter(tags=["czat"])

NO_API_KEY = "Asystent jest niedostępny: brak skonfigurowanego klucza API modelu."

AgentFactory = Callable[[str], AbstractAsyncContextManager[Orchestrator]]


def get_agent_factory(settings: Annotated[Settings, Depends(get_settings)]) -> AgentFactory:
    @asynccontextmanager
    async def factory(token: str) -> AsyncIterator[Orchestrator]:
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else ""
        if not key:
            raise AgentError(NO_API_KEY)
        llm = AnthropicLLM(key, timeout=settings.agent_timeout_s)
        async with connect(settings.mcp_url, token) as gateway:
            yield Orchestrator(llm, gateway, settings)

    return factory


def sse(event: Event) -> str:
    return f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: CurrentUserDep,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
    factory: Annotated[AgentFactory, Depends(get_agent_factory)],
) -> StreamingResponse:
    profile = await profiles_repo.get_or_create(session, user.id)
    await session.commit()
    if profile.gdpr_consent_at is None:
        raise ConsentRequiredError("Wymagana zgoda na przetwarzanie danych")
    limit = settings.chat_history_limit
    chat_input = ChatInput(
        message=body.message,
        history=[ChatTurn(t.role, t.content) for t in body.history[-limit:]] if limit else [],
        previous_categories=body.previous_categories,
        currency=profile.default_currency,
        today=date.today(),
    )

    async def stream() -> AsyncIterator[str]:
        try:
            async with factory(user.access_token) as agent:
                async for event in agent.answer(chat_input):
                    yield sse(event)
        except AgentError as exc:
            yield sse(Event("error", {"message": exc.message}))

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
