from dataclasses import dataclass, field
from typing import Any, Literal

Category = Literal["transactions", "analysis", "budgets"]
ROUTABLE: tuple[Category, ...] = ("transactions", "analysis", "budgets")
SHARED_CATEGORY = "categories"

EventType = Literal["status", "proposal", "token", "done", "error"]
Message = dict[str, Any]


class AgentError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, other: "Usage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class StepResult:
    content: list[Any]
    text: str
    tool_calls: list[ToolCall]
    usage: Usage


@dataclass(frozen=True, slots=True)
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str
