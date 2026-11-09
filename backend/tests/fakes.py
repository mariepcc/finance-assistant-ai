import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from app.agent.prompts import WORKER_ROLE
from app.agent.router import RouteDecision
from app.agent.tools import ToolDef, ToolOutcome
from app.agent.types import AgentError, Category, Message, StepResult, ToolCall, Usage

TOOL_CATEGORIES = {
    "list_categories": "categories",
    "search_transactions": "transactions",
    "propose_transaction": "transactions",
    "get_summary": "analysis",
    "get_breakdown_by_category": "analysis",
    "compare_periods": "analysis",
    "simulate_purchase": "analysis",
    "get_budget_status": "budgets",
    "propose_budget": "budgets",
}

SUMMARY = {
    "period": {"date_from": "2026-10-01", "date_to": "2026-10-31"},
    "currency": "PLN",
    "income": "6500.00",
    "expense": "7937.79",
    "balance": "-1437.79",
    "transaction_count": 57,
}
BUDGETS = {
    "month": {"date_from": "2026-11-01", "date_to": "2026-11-30"},
    "currency": "PLN",
    "budgets": [
        {"category": "Transport", "limit": "250.00", "spent": "449.71", "status": "exceeded"}
    ],
}
TX_PROPOSAL = {
    "proposal_id": "5ac5465f-279c-407e-965e-59cfc3d935e1",
    "status": "pending",
    "expires_at": "2026-11-09T16:07:38Z",
    "items": [
        {
            "type": "expense",
            "amount": "14.00",
            "currency": "PLN",
            "category": "Jedzenie",
            "occurred_on": "2026-11-09",
            "note": "kawa",
        }
    ],
    "requires_user_confirmation": True,
}


def text_step(text: str, tokens: int = 10) -> StepResult:
    return StepResult(
        content=[{"type": "text", "text": text}],
        text=text,
        tool_calls=[],
        usage=Usage(tokens, tokens),
    )


def tool_step(*calls: tuple[str, dict[str, Any]], text: str = "") -> StepResult:
    tool_calls = [
        ToolCall(id=f"call_{i}_{name}", name=name, input=args)
        for i, (name, args) in enumerate(calls)
    ]
    content: list[Any] = [{"type": "text", "text": text}] if text else []
    content += [
        {"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in tool_calls
    ]
    return StepResult(content=content, text=text, tool_calls=tool_calls, usage=Usage(10, 10))


def category_of(system: str) -> Category:
    for category, role in WORKER_ROLE.items():
        if role in system:
            return category
    raise AssertionError("nieznany prompt workera")


@dataclass
class FakeLLM:
    routes: list[RouteDecision | None] = field(default_factory=list)
    steps: dict[Category, list[StepResult]] = field(default_factory=dict)
    completions: list[str] = field(default_factory=list)
    step_delay: float = 0.0
    parse_calls: list[str] = field(default_factory=list)
    step_calls: list[tuple[Category, list[Message]]] = field(default_factory=list)
    complete_calls: list[tuple[str, str]] = field(default_factory=list)

    async def parse[T: BaseModel](
        self, *, model: str, system: str, messages: list[Message], output: type[T], effort: str
    ) -> tuple[T | None, Usage]:
        self.parse_calls.append(messages[0]["content"])
        decision = self.routes.pop(0)
        return (output.model_validate(decision.model_dump()) if decision else None), Usage(5, 5)

    async def step(
        self,
        *,
        model: str,
        system: str,
        messages: list[Message],
        tools: list[dict[str, Any]],
        effort: str,
    ) -> StepResult:
        if self.step_delay:
            await asyncio.sleep(self.step_delay)
        category = category_of(system)
        self.step_calls.append((category, [dict(m) for m in messages]))
        script = self.steps[category]
        if not script:
            raise AssertionError(f"brak kolejnego kroku dla {category}")
        return script.pop(0)

    async def complete(
        self, *, model: str, system: str, messages: list[Message], effort: str
    ) -> tuple[str, Usage]:
        self.complete_calls.append((system, messages[0]["content"]))
        return self.completions.pop(0), Usage(7, 7)


Handler = Callable[[dict[str, Any]], ToolOutcome]


def default_handlers() -> dict[str, Handler]:
    return {
        "list_categories": lambda _: ToolOutcome(
            {"categories": [{"name": "Jedzenie", "kind": "expense"}]}, False
        ),
        "get_summary": lambda _: ToolOutcome(SUMMARY, False),
        "get_budget_status": lambda _: ToolOutcome(BUDGETS, False),
        "propose_transaction": lambda _: ToolOutcome(TX_PROPOSAL, False),
    }


@dataclass
class FakeGateway:
    handlers: dict[str, Handler] = field(default_factory=default_handlers)
    fail_on_list: bool = False
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def list_tools(self) -> list[ToolDef]:
        if self.fail_on_list:
            raise AgentError("Serwer narzędzi finansowych jest niedostępny.")
        return [
            ToolDef(name=n, description=f"opis {n}", input_schema={"type": "object"}, category=c)
            for n, c in TOOL_CATEGORIES.items()
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        self.calls.append((name, arguments))
        handler = self.handlers.get(name)
        if handler is None:
            return ToolOutcome({"error": f"brak wyniku dla {name}"}, True)
        return handler(arguments)
