import asyncio
import logging
import re
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import date

from app.agent import prompts
from app.agent.editor import fix_numbers, merge_answers
from app.agent.llm import LLM
from app.agent.router import route, transcript
from app.agent.tools import ToolDef, ToolGateway
from app.agent.types import SHARED_CATEGORY, AgentError, Category, ChatTurn, Event, Usage
from app.agent.verify import allowed_numbers, unverified_numbers
from app.agent.worker import OnEvent, WorkerResult, run_worker
from app.config import Settings

logger = logging.getLogger(__name__)

TOKEN_CHUNK_WORDS = 3
TIMEOUT_MESSAGE = "Odpowiedź trwa zbyt długo. Spróbuj ponownie lub zadaj prostsze pytanie."
INTERNAL_MESSAGE = "Coś poszło nie tak po stronie asystenta. Spróbuj ponownie."


@dataclass(frozen=True, slots=True)
class ChatInput:
    message: str
    history: Sequence[ChatTurn] = ()
    previous_categories: Sequence[str] = ()
    currency: str = "PLN"
    today: date = field(default_factory=date.today)


@dataclass
class _Run:
    usage: Usage = field(default_factory=Usage)
    steps: int = 0
    categories: list[Category] = field(default_factory=list)
    results: list[WorkerResult] = field(default_factory=list)


def chunk_text(text: str, words: int = TOKEN_CHUNK_WORDS) -> list[str]:
    pieces = re.findall(r"\S+\s*", text)
    return ["".join(pieces[i : i + words]) for i in range(0, len(pieces), words)]


def worker_message(chat: ChatInput) -> str:
    if not chat.history:
        return chat.message
    return (
        f"Historia rozmowy (od najstarszej):\n<historia>\n{transcript(chat.history)}\n</historia>"
        f"\n\nAktualna wiadomość użytkownika:\n<wiadomosc>\n{chat.message}\n</wiadomosc>"
    )


class Orchestrator:
    def __init__(self, llm: LLM, gateway: ToolGateway, settings: Settings) -> None:
        self.llm = llm
        self.gateway = gateway
        self.settings = settings

    async def answer(self, chat: ChatInput) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event | None] = asyncio.Queue()

        async def emit(event: Event) -> None:
            await queue.put(event)

        async def run() -> None:
            try:
                async with asyncio.timeout(self.settings.agent_timeout_s):
                    await self._pipeline(chat, emit)
            except AgentError as exc:
                await emit(Event("error", {"message": exc.message}))
            except TimeoutError:
                await emit(Event("error", {"message": TIMEOUT_MESSAGE}))
            except Exception:
                logger.exception("agent pipeline failed")
                await emit(Event("error", {"message": INTERNAL_MESSAGE}))
            finally:
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while (event := await queue.get()) is not None:
                yield event
        finally:
            if not task.done():
                task.cancel()

    async def _pipeline(self, chat: ChatInput, emit: OnEvent) -> None:
        s = self.settings
        run = _Run()
        await emit(Event("status", {"text": prompts.STATUS_ROUTING}))
        tools = await self.gateway.list_tools()
        categories, usage = await route(
            self.llm,
            model=s.router_model,
            effort=s.router_effort,
            message=chat.message,
            history=chat.history,
            previous_categories=chat.previous_categories,
            today=chat.today,
        )
        run.usage.add(usage)
        run.steps += 1

        if categories:
            text = await self._answer_with_tools(chat, categories, tools, run, emit)
        else:
            text, usage = await self.llm.complete(
                model=s.editor_model,
                system=prompts.chat_system(chat.today),
                messages=[{"role": "user", "content": worker_message(chat)}],
                effort=s.router_effort,
            )
            run.usage.add(usage)
            run.steps += 1

        text, verified = await self._verify(chat, text or prompts.EMPTY_ANSWER, run, emit)
        for piece in chunk_text(text):
            await emit(Event("token", {"text": piece}))
        logger.info(
            "agent done categories=%s steps=%d input_tokens=%d output_tokens=%d verified=%s",
            run.categories,
            run.steps,
            run.usage.input_tokens,
            run.usage.output_tokens,
            verified,
        )
        await emit(
            Event(
                "done",
                {
                    "categories": list(run.categories),
                    "verified": verified,
                    "steps": run.steps,
                    "input_tokens": run.usage.input_tokens,
                    "output_tokens": run.usage.output_tokens,
                },
            )
        )

    async def _run_workers(
        self,
        chat: ChatInput,
        categories: Sequence[Category],
        tools: Sequence[ToolDef],
        run: _Run,
        emit: OnEvent,
    ) -> list[WorkerResult]:
        s = self.settings
        shared = [t for t in tools if t.category == SHARED_CATEGORY]

        async def one(category: Category) -> WorkerResult:
            await emit(Event("status", {"text": prompts.CATEGORY_STATUS[category]}))
            return await run_worker(
                prompts.worker_system(category, chat.today, chat.currency),
                worker_message(chat),
                [t for t in tools if t.category == category] + shared,
                s.worker_model,
                s.agent_max_steps,
                llm=self.llm,
                gateway=self.gateway,
                effort=s.worker_effort,
                on_event=emit,
            )

        results = list(await asyncio.gather(*(one(c) for c in categories)))
        run.categories += categories
        run.results += results
        for r in results:
            run.usage.add(r.usage)
            run.steps += r.steps
        return results

    async def _answer_with_tools(
        self,
        chat: ChatInput,
        categories: list[Category],
        tools: Sequence[ToolDef],
        run: _Run,
        emit: OnEvent,
    ) -> str:
        s = self.settings
        results = await self._run_workers(chat, categories, tools, run, emit)
        missing = [r.need_other_tools for r in results if r.need_other_tools]
        if missing:
            hint = (
                f"Grupy {', '.join(categories)} nie wystarczyły do odpowiedzi "
                f"({'; '.join(missing)}). Wybierz inne grupy."
            )
            extra, usage = await route(
                self.llm,
                model=s.router_model,
                effort=s.router_effort,
                message=chat.message,
                history=chat.history,
                previous_categories=chat.previous_categories,
                today=chat.today,
                hint=hint,
                exclude=categories,
            )
            run.usage.add(usage)
            run.steps += 1
            if extra:
                results = [r for r in results if not r.need_other_tools]
                results += await self._run_workers(chat, extra, tools, run, emit)

        answers = [r.text for r in results if r.text and not r.need_other_tools]
        if not answers:
            answers = [r.text for r in results if r.text]
        if len(answers) <= 1:
            return answers[0] if answers else prompts.EMPTY_ANSWER
        await emit(Event("status", {"text": prompts.STATUS_EDITING}))
        text, usage = await merge_answers(
            self.llm,
            model=s.editor_model,
            effort=s.router_effort,
            question=chat.message,
            answers=answers,
        )
        run.usage.add(usage)
        run.steps += 1
        return text

    async def _verify(
        self, chat: ChatInput, text: str, run: _Run, emit: OnEvent
    ) -> tuple[str, bool]:
        s = self.settings
        tool_data = [rec.data for r in run.results for rec in r.records if not rec.is_error]
        user_texts = [chat.message] + [t.content for t in chat.history if t.role == "user"]
        allowed = allowed_numbers(tool_data, user_texts, chat.today)
        unverified = unverified_numbers(text, allowed)
        if not unverified:
            return text, True
        await emit(Event("status", {"text": prompts.STATUS_VERIFYING}))
        logger.info("agent unverified numbers=%s", unverified)
        fixed, usage = await fix_numbers(
            self.llm,
            model=s.editor_model,
            effort=s.router_effort,
            answer=text,
            unverified=unverified,
            tool_data=tool_data,
        )
        run.usage.add(usage)
        run.steps += 1
        if fixed and not unverified_numbers(fixed, allowed):
            return fixed, True
        return prompts.UNVERIFIED_ANSWER, False
