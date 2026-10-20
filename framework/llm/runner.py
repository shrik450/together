"""Run Pydantic AI agents with the app's model roles and run records.

Modules define plain Pydantic AI agents without a model and run them through
`run_agent`, which picks the model for the requested role and records every
run in `llm_runs`. Runs can take minutes, so records are written in their own
short sessions rather than a request's session.
"""

from __future__ import annotations

import dataclasses
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from litestar import Litestar
from pydantic_ai import (
    Agent,
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    UsageLimits,
    UserContent,
    UserPromptPart,
    capture_run_messages,
)
from sqlalchemy import update

from framework.db import open_async_session
from framework.llm.models import LlmRun, LlmRunStatus
from framework.llm.roles import ModelRole, resolve_model

DEFAULT_USAGE_LIMITS = UsageLimits(request_limit=30)


@dataclass(frozen=True, slots=True)
class AgentResult[OutputT]:
    output: OutputT
    run_id: int


class AgentRunFailed(Exception):
    def __init__(self, run_id: int, message: str) -> None:
        super().__init__(message)
        self.run_id: int = run_id


async def run_agent[DepsT, OutputT](
    agent: Agent[DepsT, OutputT],
    prompt: str | Sequence[UserContent],
    *,
    deps: DepsT,
    role: ModelRole = ModelRole.default,
    message_history: Sequence[ModelMessage] = (),
    usage_limits: UsageLimits = DEFAULT_USAGE_LIMITS,
) -> AgentResult[OutputT]:
    if agent.name is None:
        raise ValueError("Agents must be named to be recorded")

    model = resolve_model(role)
    run_id = await _start_run(agent.name, model)
    with capture_run_messages() as messages:
        try:
            result = await agent.run(
                prompt,
                deps=deps,
                model=model,
                message_history=list(message_history),
                usage_limits=usage_limits,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            await _finish_run(
                run_id,
                LlmRunStatus.failed,
                messages,
                history_length=len(message_history),
                error=error,
            )
            raise AgentRunFailed(run_id, error) from exc

    await _finish_run(
        run_id,
        LlmRunStatus.succeeded,
        result.all_messages(),
        history_length=len(message_history),
    )
    return AgentResult(output=result.output, run_id=run_id)


@asynccontextmanager
async def llm_lifespan(_app: Litestar) -> AsyncGenerator[None]:
    """Mark runs cut off by the last shutdown or crash as interrupted.

    The app runs as a single process, so no run is in progress at startup.
    """
    async with open_async_session() as session:
        await session.execute(
            update(LlmRun)
            .where(LlmRun.status == LlmRunStatus.running)
            .values(status=LlmRunStatus.interrupted, finished_at=datetime.now(UTC))
        )
        await session.commit()
    yield


async def _start_run(agent: str, model: str) -> int:
    async with open_async_session() as session:
        run = LlmRun(agent=agent, model=model, status=LlmRunStatus.running)
        session.add(run)
        await session.commit()
        return run.id


async def _finish_run(
    run_id: int,
    status: LlmRunStatus,
    messages: Sequence[ModelMessage],
    *,
    history_length: int,
    error: str | None = None,
) -> None:
    # Messages start with the history the run continued from; only the rest
    # was spent by this run.
    responses = [
        message
        for message in messages[history_length:]
        if isinstance(message, ModelResponse)
    ]
    async with open_async_session() as session:
        run = await session.get_one(LlmRun, run_id)
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.requests = len(responses)
        run.input_tokens = sum(response.usage.input_tokens for response in responses)
        run.output_tokens = sum(response.usage.output_tokens for response in responses)
        run.cost_usd = _total_cost(responses)
        run.error = error
        run.messages = without_binary_content(messages)
        await session.commit()


def _total_cost(responses: Sequence[ModelResponse]) -> Decimal | None:
    """Sum the responses' costs, or None if any response couldn't be priced."""
    total = Decimal(0)
    for response in responses:
        if response.usage.cost is None:
            return None
        total += response.usage.cost
    return total


def without_binary_content(messages: Sequence[ModelMessage]) -> list[ModelMessage]:
    """Replace images and other files in prompts with a note of their type.

    Inputs like receipt photos are meant to be discarded once read, so they
    must not be kept in the run record.
    """
    return [
        dataclasses.replace(
            message, parts=[_without_binary_part(part) for part in message.parts]
        )
        if isinstance(message, ModelRequest)
        else message
        for message in messages
    ]


def _without_binary_part(part: ModelRequestPart) -> ModelRequestPart:
    if not isinstance(part, UserPromptPart) or isinstance(part.content, str):
        return part
    return dataclasses.replace(
        part,
        content=[
            f"[{item.media_type} omitted]" if isinstance(item, BinaryContent) else item
            for item in part.content
        ],
    )
