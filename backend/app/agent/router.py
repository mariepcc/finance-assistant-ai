from collections.abc import Sequence
from datetime import date

from pydantic import BaseModel, Field

from app.agent.llm import LLM
from app.agent.prompts import ROUTER_SYSTEM, today_line
from app.agent.types import ROUTABLE, Category, ChatTurn, Usage


class RouteDecision(BaseModel):
    categories: list[Category] = Field(
        default_factory=list,
        description="0–2 grupy narzędzi; pusta lista oznacza zwykłą rozmowę",
    )
    reason: str = Field(default="", description="Krótkie uzasadnienie wyboru")


def transcript(history: Sequence[ChatTurn]) -> str:
    speaker = {"user": "Użytkownik", "assistant": "Asystent"}
    return "\n".join(f"{speaker[t.role]}: {t.content}" for t in history)


def router_prompt(
    message: str,
    history: Sequence[ChatTurn],
    previous_categories: Sequence[str],
    today: date,
    hint: str | None = None,
) -> str:
    parts = [today_line(today)]
    if previous_categories:
        parts.append(f"Poprzednio użyte grupy: {', '.join(previous_categories)}")
    if history:
        parts.append(
            f"Historia rozmowy (od najstarszej):\n<historia>\n{transcript(history)}\n</historia>"
        )
    if hint:
        parts.append(hint)
    parts.append(f"Ostatnia wiadomość użytkownika:\n<wiadomosc>\n{message}\n</wiadomosc>")
    return "\n\n".join(parts)


def normalize(categories: Sequence[str], exclude: Sequence[str] = ()) -> list[Category]:
    result: list[Category] = []
    for name in categories:
        for allowed in ROUTABLE:
            if name == allowed and allowed not in result and allowed not in exclude:
                result.append(allowed)
    return result[:2]


async def route(
    llm: LLM,
    *,
    model: str,
    effort: str,
    message: str,
    history: Sequence[ChatTurn],
    previous_categories: Sequence[str],
    today: date,
    hint: str | None = None,
    exclude: Sequence[str] = (),
) -> tuple[list[Category], Usage]:
    prompt = router_prompt(message, history, previous_categories, today, hint)
    decision, usage = await llm.parse(
        model=model,
        system=ROUTER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output=RouteDecision,
        effort=effort,
    )
    if decision is None:
        return [], usage
    return normalize(decision.categories, exclude), usage
