import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.agent.llm import LLM
from app.agent.prompts import STEP_LIMIT_ANSWER, TOOL_STATUS
from app.agent.tools import ToolDef, ToolGateway, ToolOutcome
from app.agent.types import Event, Message, ToolCall, Usage

NEED_OTHER_TOOLS = "need_other_tools"
NEED_OTHER_TOOLS_DEF: dict[str, Any] = {
    "name": NEED_OTHER_TOOLS,
    "description": (
        "Wywołaj, gdy do odpowiedzi potrzebne są narzędzia, których nie masz "
        "(np. pytanie o budżety, a masz tylko narzędzia transakcji)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"reason": {"type": "string", "description": "Czego brakuje"}},
        "required": ["reason"],
        "additionalProperties": False,
    },
}
PROPOSAL_KINDS = {"propose_transaction": "transaction", "propose_budget": "budget"}

OnEvent = Callable[[Event], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class ToolRecord:
    name: str
    input: dict[str, Any]
    data: Any
    is_error: bool


@dataclass
class WorkerResult:
    text: str
    records: list[ToolRecord] = field(default_factory=list)
    proposals: list[dict[str, Any]] = field(default_factory=list)
    need_other_tools: str | None = None
    steps: int = 0
    usage: Usage = field(default_factory=Usage)
    hit_step_limit: bool = False


async def _noop(_: Event) -> None:
    return None


async def run_worker(
    system_prompt: str,
    user_message: str,
    tools: list[ToolDef],
    model: str,
    max_steps: int,
    *,
    llm: LLM,
    gateway: ToolGateway,
    effort: str,
    on_event: OnEvent = _noop,
) -> WorkerResult:
    allowed = {t.name for t in tools}
    api_tools = [t.to_api() for t in tools] + [NEED_OTHER_TOOLS_DEF]
    messages: list[Message] = [{"role": "user", "content": user_message}]
    result = WorkerResult(text="")

    async def execute(call: ToolCall) -> ToolOutcome:
        if call.name not in allowed:
            outcome = ToolOutcome({"error": f"Narzędzie {call.name} nie jest dostępne"}, True)
        else:
            await on_event(Event("status", {"text": TOOL_STATUS.get(call.name, "Pracuję…")}))
            outcome = await gateway.call(call.name, call.input)
        result.records.append(ToolRecord(call.name, call.input, outcome.data, outcome.is_error))
        kind = PROPOSAL_KINDS.get(call.name)
        if kind and not outcome.is_error and isinstance(outcome.data, dict):
            proposal = {"kind": kind, **outcome.data}
            result.proposals.append(proposal)
            await on_event(Event("proposal", proposal))
        return outcome

    for _ in range(max_steps):
        step = await llm.step(
            model=model, system=system_prompt, messages=messages, tools=api_tools, effort=effort
        )
        result.steps += 1
        result.usage.add(step.usage)
        if not step.tool_calls:
            result.text = step.text
            return result
        other = next((c for c in step.tool_calls if c.name == NEED_OTHER_TOOLS), None)
        if other is not None:
            result.need_other_tools = str(other.input.get("reason", "")) or "brak narzędzi"
            result.text = step.text
            return result
        messages.append({"role": "assistant", "content": step.content})
        outcomes = await asyncio.gather(*(execute(c) for c in step.tool_calls))
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": json.dumps(outcome.data, ensure_ascii=False),
                        "is_error": outcome.is_error,
                    }
                    for call, outcome in zip(step.tool_calls, outcomes, strict=True)
                ],
            }
        )

    result.text = STEP_LIMIT_ANSWER
    result.hit_step_limit = True
    return result
