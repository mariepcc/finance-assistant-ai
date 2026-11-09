import json
from collections.abc import Sequence
from typing import Any

from app.agent.llm import LLM
from app.agent.prompts import EDITOR_SYSTEM, FIX_SYSTEM
from app.agent.types import Usage


async def merge_answers(
    llm: LLM, *, model: str, effort: str, question: str, answers: Sequence[str]
) -> tuple[str, Usage]:
    parts = [f"Pytanie użytkownika:\n<pytanie>\n{question}\n</pytanie>"]
    parts += [
        f"Odpowiedź {i}:\n<odpowiedz>\n{text}\n</odpowiedz>" for i, text in enumerate(answers, 1)
    ]
    return await llm.complete(
        model=model,
        system=EDITOR_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
        effort=effort,
    )


async def fix_numbers(
    llm: LLM,
    *,
    model: str,
    effort: str,
    answer: str,
    unverified: Sequence[str],
    tool_data: Sequence[Any],
) -> tuple[str, Usage]:
    content = (
        f"Odpowiedź do poprawy:\n<odpowiedz>\n{answer}\n</odpowiedz>\n\n"
        f"Liczby bez pokrycia w wynikach: {', '.join(unverified)}\n\n"
        f"Wyniki narzędzi:\n<wyniki>\n{json.dumps(list(tool_data), ensure_ascii=False)}\n</wyniki>"
    )
    return await llm.complete(
        model=model,
        system=FIX_SYSTEM,
        messages=[{"role": "user", "content": content}],
        effort=effort,
    )
