from typing import Any, Protocol, cast

import anthropic
from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.agent.types import AgentError, Message, StepResult, ToolCall, Usage

ROUTER_MAX_TOKENS = 2048
WORKER_MAX_TOKENS = 8000
TEXT_MAX_TOKENS = 4000


class LLM(Protocol):
    async def parse[T: BaseModel](
        self, *, model: str, system: str, messages: list[Message], output: type[T], effort: str
    ) -> tuple[T | None, Usage]: ...

    async def step(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        effort: str,
    ) -> StepResult: ...

    async def complete(
        self, *, model: str, system: str, messages: list[Message], effort: str
    ) -> tuple[str, Usage]: ...


def _usage(raw: Any) -> Usage:
    return Usage(input_tokens=raw.input_tokens or 0, output_tokens=raw.output_tokens or 0)


def _text(content: list[Any]) -> str:
    return "".join(b.text for b in content if getattr(b, "type", None) == "text").strip()


def _check_stop(stop_reason: str | None) -> None:
    if stop_reason == "refusal":
        raise AgentError("Model odmówił odpowiedzi na to pytanie.")
    if stop_reason == "max_tokens":
        raise AgentError("Odpowiedź modelu okazała się za długa. Spróbuj zadać węższe pytanie.")


def _api_error(exc: anthropic.AnthropicError) -> AgentError:
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return AgentError("Asystent jest niedostępny: nieprawidłowy klucz API.")
    if isinstance(exc, anthropic.RateLimitError):
        return AgentError("Za dużo zapytań do modelu. Spróbuj za chwilę.")
    if isinstance(exc, anthropic.APITimeoutError | anthropic.APIConnectionError):
        return AgentError("Brak połączenia z modelem językowym. Spróbuj ponownie.")
    return AgentError("Model językowy jest chwilowo niedostępny. Spróbuj ponownie.")


class AnthropicLLM:
    def __init__(self, api_key: str, timeout: float) -> None:
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=2)

    async def parse[T: BaseModel](
        self, *, model: str, system: str, messages: list[Message], output: type[T], effort: str
    ) -> tuple[T | None, Usage]:
        try:
            response = await self._client.messages.parse(
                model=model,
                max_tokens=ROUTER_MAX_TOKENS,
                system=system,
                messages=cast(Any, messages),
                output_format=output,
                output_config=cast(Any, {"effort": effort}),
            )
        except anthropic.AnthropicError as exc:
            raise _api_error(exc) from exc
        except ValueError:
            return None, Usage()
        _check_stop(response.stop_reason)
        return response.parsed_output, _usage(response.usage)

    async def step(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        effort: str,
    ) -> StepResult:
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=WORKER_MAX_TOKENS,
                system=system,
                messages=cast(Any, messages),
                tools=cast(Any, tools),
                output_config=cast(Any, {"effort": effort}),
            )
        except anthropic.AnthropicError as exc:
            raise _api_error(exc) from exc
        _check_stop(response.stop_reason)
        calls = [
            ToolCall(id=b.id, name=b.name, input=dict(b.input))
            for b in response.content
            if b.type == "tool_use"
        ]
        return StepResult(
            content=list(response.content),
            text=_text(list(response.content)),
            tool_calls=calls,
            usage=_usage(response.usage),
        )

    async def complete(
        self, *, model: str, system: str, messages: list[Message], effort: str
    ) -> tuple[str, Usage]:
        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=TEXT_MAX_TOKENS,
                system=system,
                messages=cast(Any, messages),
                output_config=cast(Any, {"effort": effort}),
            )
        except anthropic.AnthropicError as exc:
            raise _api_error(exc) from exc
        _check_stop(response.stop_reason)
        return _text(list(response.content)), _usage(response.usage)
