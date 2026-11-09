from datetime import date

from app.agent.router import RouteDecision, normalize, route
from app.agent.types import ChatTurn
from tests.fakes import FakeLLM

TODAY = date(2026, 11, 9)


def test_normalize_dedupes_limits_and_excludes() -> None:
    assert normalize(["analysis", "analysis", "budgets", "transactions"]) == [
        "analysis",
        "budgets",
    ]
    assert normalize(["chat", "reports"]) == []
    assert normalize(["analysis", "budgets"], exclude=["analysis"]) == ["budgets"]


async def test_route_returns_categories_and_passes_context() -> None:
    llm = FakeLLM(routes=[RouteDecision(categories=["analysis"], reason="sumy")])
    history = [
        ChatTurn("user", "Ile wydałam w październiku?"),
        ChatTurn("assistant", "7937,79 zł."),
    ]
    categories, usage = await route(
        llm,
        model="m",
        effort="low",
        message="a we wrześniu?",
        history=history,
        previous_categories=["analysis"],
        today=TODAY,
    )
    assert categories == ["analysis"]
    assert usage.input_tokens == 5
    prompt = llm.parse_calls[0]
    assert "Poprzednio użyte grupy: analysis" in prompt
    assert "Użytkownik: Ile wydałam w październiku?" in prompt
    assert "<wiadomosc>\na we wrześniu?\n</wiadomosc>" in prompt
    assert "2026-11-09" in prompt


async def test_invalid_router_output_means_chat() -> None:
    llm = FakeLLM(routes=[None])
    categories, _ = await route(
        llm,
        model="m",
        effort="low",
        message="hej",
        history=[],
        previous_categories=[],
        today=TODAY,
    )
    assert categories == []
