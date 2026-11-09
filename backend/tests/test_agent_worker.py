import json
from datetime import date

from app.agent.prompts import STEP_LIMIT_ANSWER, worker_system
from app.agent.tools import ToolOutcome
from app.agent.types import Category, Event
from app.agent.worker import NEED_OTHER_TOOLS, WorkerResult, run_worker
from tests.fakes import SUMMARY, TX_PROPOSAL, FakeGateway, FakeLLM, text_step, tool_step

TODAY = date(2026, 11, 9)


async def run(
    llm: FakeLLM,
    gateway: FakeGateway,
    category: Category = "analysis",
    max_steps: int = 4,
    events: list[Event] | None = None,
) -> WorkerResult:
    tools = [t for t in await gateway.list_tools() if t.category in (category, "categories")]
    sink = events if events is not None else []

    async def on_event(e: Event) -> None:
        sink.append(e)

    return await run_worker(
        worker_system(category, TODAY, "PLN"),
        "Ile wydałam w październiku?",
        tools,
        "m",
        max_steps,
        llm=llm,
        gateway=gateway,
        effort="low",
        on_event=on_event,
    )


async def test_answer_without_tools() -> None:
    llm = FakeLLM(steps={"analysis": [text_step("Cześć!")]})
    result = await run(llm, FakeGateway())
    assert result.text == "Cześć!"
    assert result.steps == 1
    assert result.records == []


async def test_tool_call_result_goes_back_to_model() -> None:
    llm = FakeLLM(
        steps={
            "analysis": [
                tool_step(("get_summary", {"date_from": "2026-10-01", "date_to": "2026-10-31"})),
                text_step("Wydałaś 7937,79 zł."),
            ]
        }
    )
    gateway = FakeGateway()
    events: list[Event] = []
    result = await run(llm, gateway, events=events)

    assert result.text == "Wydałaś 7937,79 zł."
    assert gateway.calls == [("get_summary", {"date_from": "2026-10-01", "date_to": "2026-10-31"})]
    assert result.records[0].data == SUMMARY
    assert result.usage.input_tokens == 20
    _, messages = llm.step_calls[1]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    tool_result = messages[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "call_0_get_summary"
    assert json.loads(tool_result["content"]) == SUMMARY
    assert tool_result["is_error"] is False
    assert Event("status", {"text": "Liczę sumy…"}) in events


async def test_parallel_calls_return_in_one_message() -> None:
    llm = FakeLLM(
        steps={
            "analysis": [
                tool_step(("get_summary", {"a": 1}), ("list_categories", {})),
                text_step("ok"),
            ]
        }
    )
    gateway = FakeGateway()
    await run(llm, gateway)
    assert sorted(name for name, _ in gateway.calls) == ["get_summary", "list_categories"]
    results = llm.step_calls[1][1][2]["content"]
    assert [r["tool_use_id"] for r in results] == ["call_0_get_summary", "call_1_list_categories"]


async def test_tool_outside_category_is_rejected() -> None:
    llm = FakeLLM(
        steps={"analysis": [tool_step(("propose_budget", {"amount": 1})), text_step("Nie mogę.")]}
    )
    gateway = FakeGateway()
    result = await run(llm, gateway)
    assert gateway.calls == []
    assert result.records[0].is_error
    assert llm.step_calls[1][1][2]["content"][0]["is_error"] is True


async def test_tool_error_is_passed_as_error_result() -> None:
    gateway = FakeGateway()
    gateway.handlers["get_summary"] = lambda _: ToolOutcome(
        {"error": "Data początkowa nie może być późniejsza niż końcowa"}, True
    )
    llm = FakeLLM(steps={"analysis": [tool_step(("get_summary", {})), text_step("Błędny okres.")]})
    result = await run(llm, gateway)
    assert result.records[0].is_error
    sent = llm.step_calls[1][1][2]["content"][0]
    assert sent["is_error"] is True
    assert "późniejsza" in sent["content"]


async def test_step_limit_stops_the_loop() -> None:
    llm = FakeLLM(steps={"analysis": [tool_step(("get_summary", {})) for _ in range(3)]})
    result = await run(llm, FakeGateway(), max_steps=3)
    assert result.hit_step_limit
    assert result.text == STEP_LIMIT_ANSWER
    assert result.steps == 3


async def test_need_other_tools_stops_worker() -> None:
    llm = FakeLLM(
        steps={"analysis": [tool_step((NEED_OTHER_TOOLS, {"reason": "pytanie o budżety"}))]}
    )
    gateway = FakeGateway()
    result = await run(llm, gateway)
    assert result.need_other_tools == "pytanie o budżety"
    assert gateway.calls == []


async def test_proposal_is_emitted_as_event() -> None:
    llm = FakeLLM(
        steps={
            "transactions": [
                tool_step(("propose_transaction", {"items": []})),
                text_step("Kawa 14,00 zł czeka na potwierdzenie."),
            ]
        }
    )
    events: list[Event] = []
    result = await run(llm, FakeGateway(), category="transactions", events=events)
    proposal = {"kind": "transaction", **TX_PROPOSAL}
    assert result.proposals == [proposal]
    assert Event("proposal", proposal) in events
