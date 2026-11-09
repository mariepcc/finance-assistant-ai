from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from fastmcp import Client

from app.agent.types import AgentError

UNAVAILABLE = "Serwer narzędzi finansowych jest niedostępny. Spróbuj ponownie za chwilę."


@dataclass(frozen=True, slots=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    category: str

    def to_api(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    data: Any
    is_error: bool


class ToolGateway(Protocol):
    async def list_tools(self) -> list[ToolDef]: ...

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome: ...


def _category(meta: dict[str, Any] | None) -> str:
    value = (meta or {}).get("category")
    return value if isinstance(value, str) else ""


class MCPToolGateway:
    def __init__(self, client: Client[Any]) -> None:
        self._client = client

    async def list_tools(self) -> list[ToolDef]:
        try:
            tools = await self._client.list_tools()
        except Exception as exc:
            raise AgentError(UNAVAILABLE) from exc
        return [
            ToolDef(
                name=t.name,
                description=t.description or "",
                input_schema=dict(t.input_schema),
                category=_category(t.meta),
            )
            for t in tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        try:
            result = await self._client.call_tool(name, arguments, raise_on_error=False)
        except Exception as exc:
            raise AgentError(UNAVAILABLE) from exc
        if result.is_error:
            message = " ".join(getattr(c, "text", "") for c in result.content).strip()
            return ToolOutcome({"error": message or "Błąd narzędzia"}, is_error=True)
        return ToolOutcome(result.structured_content, is_error=False)


@asynccontextmanager
async def connect(url: str, token: str) -> AsyncIterator[MCPToolGateway]:
    client: Client[Any] = Client(url, auth=token)
    async with AsyncExitStack() as stack:
        try:
            await stack.enter_async_context(client)
        except Exception as exc:
            raise AgentError(UNAVAILABLE) from exc
        yield MCPToolGateway(client)
