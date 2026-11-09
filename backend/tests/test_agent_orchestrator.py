from datetime import date
from typing import Any

from app.agent import prompts
from app.agent.orchestrator import TIMEOUT_MESSAGE, ChatInput, Orchestrator, chunk_text
from app.agent.router import RouteDecision
from app.agent.types import ChatTurn, Event
from app.agent.worker import NEED_OTHER_TOOLS
from app.config import Settings
from tests.fakes import TX_PROPOSAL, FakeGateway, FakeLLM, text_step, tool_step

TODAY = date(2026, 11, 9)
SUMMARY_CALL = ("get_summary", {"date_from": "2026-10-01", "date_to": "2026-10-31"})


def routes(*groups: list[str]) -> list[RouteDecision | None]:
    return [RouteDecision.model_validate({"categories": g}) for g in groups]


async def collect(
    llm: FakeLLM,
    gateway: FakeGateway | None = None,
    message: str = "Ile wydałam w październiku?",
    history: list[ChatTurn] | None = None,
    **overrides: Any,
) -> list[Event]:
    config = Settings.model_validate({"anthropic_api_key": None, **overrides})
    orchestrator = Orchestrator(llm, gateway or FakeGateway(), config)
    chat = ChatInput(message=message, history=history or [], today=TODAY)
    return [e async for e in orchestrator.answer(chat)]


def text_of(events: list[Event]) -> str:
    return "".join(e.data["text"] for e in events if e.type == "token")


def done(events: list[Event]) -> dict[str, Any]:
    assert events[-1].type == "done", events[-1]
    return events[-1].data


def statuses(events: list[Event]) -> list[str]:
    return [e.data["text"] for e in events if e.type == "status"]


def test_chunk_text_keeps_whitespace() -> None:
    text = "Wydałaś 7937,79 zł w październiku,\nczyli więcej niż we wrześniu."
    chunks = chunk_text(text, words=2)
    assert "".join(chunks) == text
    assert len(chunks) == 5


async def test_chat_without_tools() -> None:
    llm = FakeLLM(routes=routes([]), completions=["Cześć! Pomagam w finansach."])
    events = await collect(llm, message="Cześć")
    assert text_of(events) == "Cześć! Pomagam w finansach."
    assert done(events)["categories"] == []
    assert done(events)["verified"] is True
    assert llm.step_calls == []
    assert "nie podawaj żadnych kwot" in llm.complete_calls[0][0]


async def test_single_worker_answer_is_streamed_after_verification() -> None:
    llm = FakeLLM(
        routes=routes(["analysis"]),
        steps={"analysis": [tool_step(SUMMARY_CALL), text_step("Wydałaś 7937,79 zł.")]},
    )
    events = await collect(llm)
    assert events[0] == Event("status", {"text": prompts.STATUS_ROUTING})
    assert text_of(events) == "Wydałaś 7937,79 zł."
    info = done(events)
    assert info["categories"] == ["analysis"]
    assert info["verified"] is True
    assert info["steps"] == 3
    assert llm.complete_calls == []


async def test_two_workers_run_and_editor_merges() -> None:
    llm = FakeLLM(
        routes=routes(["analysis", "budgets"]),
        steps={
            "analysis": [tool_step(SUMMARY_CALL), text_step("Wydatki: 7937,79 zł.")],
            "budgets": [tool_step(("get_budget_status", {})), text_step("Transport: 449,71 zł.")],
        },
        completions=["Wydatki to 7937,79 zł, a na transport poszło 449,71 zł."],
    )
    events = await collect(llm)
    assert prompts.STATUS_EDITING in statuses(events)
    assert text_of(events) == "Wydatki to 7937,79 zł, a na transport poszło 449,71 zł."
    editor_input = llm.complete_calls[0][1]
    assert "Wydatki: 7937,79 zł." in editor_input
    assert "Transport: 449,71 zł." in editor_input
    assert done(events)["categories"] == ["analysis", "budgets"]


async def test_proposal_event_comes_before_answer() -> None:
    llm = FakeLLM(
        routes=routes(["transactions"]),
        steps={
            "transactions": [
                tool_step(("propose_transaction", {"items": []})),
                text_step("Kawa za 14,00 zł czeka na Twoje potwierdzenie."),
            ]
        },
    )
    events = await collect(llm, message="kawa 14 zł")
    types = [e.type for e in events]
    assert types.index("proposal") < types.index("token")
    proposal = next(e for e in events if e.type == "proposal")
    assert proposal.data == {"kind": "transaction", **TX_PROPOSAL}
    assert done(events)["verified"] is True


async def test_need_other_tools_reroutes_once() -> None:
    llm = FakeLLM(
        routes=routes(["transactions"], ["budgets"]),
        steps={
            "transactions": [tool_step((NEED_OTHER_TOOLS, {"reason": "pytanie o limity"}))],
            "budgets": [tool_step(("get_budget_status", {})), text_step("Limit: 250,00 zł.")],
        },
    )
    events = await collect(llm, message="Jak stoją budżety?")
    assert text_of(events) == "Limit: 250,00 zł."
    assert "pytanie o limity" in llm.parse_calls[1]
    assert done(events)["categories"] == ["transactions", "budgets"]


async def test_unverified_number_is_fixed_once() -> None:
    llm = FakeLLM(
        routes=routes(["analysis"]),
        steps={"analysis": [tool_step(SUMMARY_CALL), text_step("Wydałaś około 7938 zł.")]},
        completions=["Wydałaś 7937,79 zł."],
    )
    events = await collect(llm)
    assert prompts.STATUS_VERIFYING in statuses(events)
    assert text_of(events) == "Wydałaś 7937,79 zł."
    assert done(events)["verified"] is True
    assert "7938" in llm.complete_calls[0][1]


async def test_still_unverified_answer_is_replaced_with_honest_message() -> None:
    llm = FakeLLM(
        routes=routes(["analysis"]),
        steps={"analysis": [tool_step(SUMMARY_CALL), text_step("Wydałaś około 7938 zł.")]},
        completions=["Wydałaś prawie 8000 zł."],
    )
    events = await collect(llm)
    assert text_of(events) == prompts.UNVERIFIED_ANSWER
    assert done(events)["verified"] is False


async def test_numbers_without_tool_calls_are_not_trusted() -> None:
    llm = FakeLLM(
        routes=routes(["analysis"]),
        steps={"analysis": [text_step("Wydałaś 1234,56 zł.")]},
        completions=["Wydałaś 1234,56 zł."],
    )
    events = await collect(llm)
    assert done(events)["verified"] is False


async def test_gateway_failure_becomes_error_event() -> None:
    events = await collect(FakeLLM(), FakeGateway(fail_on_list=True))
    assert events[-1].type == "error"
    assert "niedostępny" in events[-1].data["message"]


async def test_timeout_becomes_error_event() -> None:
    llm = FakeLLM(
        routes=routes(["analysis"]),
        steps={"analysis": [text_step("x")]},
        step_delay=0.5,
    )
    events = await collect(llm, agent_timeout_s=0.05)
    assert events[-1] == Event("error", {"message": TIMEOUT_MESSAGE})
