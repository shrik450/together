from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pytest
from litestar import Litestar
from pydantic_ai import (
    Agent,
    BinaryContent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from framework.browser import BrowserService, Link, Page
from framework.db import open_async_session
from framework.llm import (
    AgentRunFailed,
    LlmRun,
    LlmRunStatus,
    ModelRole,
    llm_lifespan,
    resolve_model,
    run_agent,
    web_toolset,
)
from framework.llm.runner import without_binary_content
from framework.llm.tools import format_page


@dataclass
class Dish:
    name: str
    verdict: str


def _fetch_then_echo(url: str) -> FunctionModel:
    """A model that fetches `url`, then answers with what the tool returned."""

    def respond(messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        returns = [
            part
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("fetch_page", {"url": url})])
        return ModelResponse(parts=[TextPart(str(returns[0].content))])

    return FunctionModel(respond)


async def _get_run(run_id: int) -> LlmRun:
    async with open_async_session() as session:
        return await session.get_one(LlmRun, run_id)


def _first_prompt(run: LlmRun) -> str | Sequence[UserContent]:
    assert run.messages is not None
    request = run.messages[0]
    assert isinstance(request, ModelRequest)
    part = request.parts[0]
    assert isinstance(part, UserPromptPart)
    return part.content


def _broken_model(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
    raise RuntimeError("provider exploded")


def _answer_once_then_break() -> Callable[
    [list[ModelMessage], AgentInfo], ModelResponse
]:
    """A model whose first response calls a missing tool, and whose retry fails."""
    calls = 0

    def respond(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise RuntimeError("provider exploded")
        return ModelResponse(parts=[ToolCallPart("missing_tool", {})])

    return respond


class TestModelRoles:
    def test_roles_have_code_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TOGETHER_LLM_MODEL_DEFAULT", raising=False)

        assert resolve_model(ModelRole.default) == "anthropic:claude-opus-5-5"

    def test_environment_overrides_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOGETHER_LLM_MODEL_FAST", "openai:some-model")

        assert resolve_model(ModelRole.fast) == "openai:some-model"


class TestRunAgent:
    async def test_records_successful_run(self, reset_database: None) -> None:
        agent = Agent(name="test.dish", output_type=Dish)

        with agent.override(model=TestModel()):
            result = await run_agent(agent, "Khachapuri was great", deps=None)

        assert isinstance(result.output, Dish)
        run = await _get_run(result.run_id)
        assert run.agent == "test.dish"
        assert run.model == resolve_model(ModelRole.default)
        assert run.status is LlmRunStatus.succeeded
        assert run.finished_at is not None
        assert run.requests == 1
        assert run.input_tokens > 0
        assert run.cost_usd is None  # TestModel has no price
        assert run.error is None
        assert _first_prompt(run) == "Khachapuri was great"

    async def test_continued_run_records_only_its_own_usage(
        self, reset_database: None
    ) -> None:
        agent = Agent(name="test.chat")

        with agent.override(model=TestModel()):
            first = await run_agent(agent, "first", deps=None)
            history = (await _get_run(first.run_id)).messages
            assert history is not None
            second = await run_agent(
                agent, "second", deps=None, message_history=history
            )

        second_run = await _get_run(second.run_id)
        assert second_run.requests == 1
        assert second_run.messages is not None
        assert len(second_run.messages) == len(history) + 2

    async def test_failed_continued_run_records_only_its_own_usage(
        self, reset_database: None
    ) -> None:
        agent = Agent(name="test.chat")
        with agent.override(model=TestModel()):
            first = await run_agent(agent, "first", deps=None)
        history = (await _get_run(first.run_id)).messages
        assert history is not None

        with (
            agent.override(model=FunctionModel(_answer_once_then_break())),
            pytest.raises(AgentRunFailed) as caught,
        ):
            await run_agent(agent, "second", deps=None, message_history=history)

        assert (await _get_run(caught.value.run_id)).requests == 1

    async def test_records_failed_run(self, reset_database: None) -> None:
        agent = Agent(name="test.broken")

        with (
            agent.override(model=FunctionModel(_broken_model)),
            pytest.raises(AgentRunFailed, match="provider exploded") as caught,
        ):
            await run_agent(agent, "hello", deps=None)

        run = await _get_run(caught.value.run_id)
        assert run.status is LlmRunStatus.failed
        assert run.error == "RuntimeError: provider exploded"
        assert run.finished_at is not None

    async def test_does_not_store_images(self, reset_database: None) -> None:
        agent = Agent(name="test.receipt")
        receipt = BinaryContent(data=b"\x89PNG receipt", media_type="image/png")

        with agent.override(model=TestModel()):
            result = await run_agent(agent, ["Read this receipt", receipt], deps=None)

        run = await _get_run(result.run_id)
        assert _first_prompt(run) == ["Read this receipt", "[image/png omitted]"]

    async def test_rejects_unnamed_agents(self) -> None:
        with pytest.raises(ValueError, match="must be named"):
            await run_agent(Agent(), "hello", deps=None)


class TestInterruptedRuns:
    async def test_startup_marks_unfinished_runs_interrupted(
        self, reset_database: None, litestar_app: Litestar
    ) -> None:
        async with open_async_session() as session:
            unfinished = LlmRun(agent="a", model="m", status=LlmRunStatus.running)
            finished = LlmRun(agent="a", model="m", status=LlmRunStatus.succeeded)
            session.add_all([unfinished, finished])
            await session.commit()

        async with llm_lifespan(litestar_app):
            pass

        unfinished_run = await _get_run(unfinished.id)
        assert unfinished_run.status is LlmRunStatus.interrupted
        assert unfinished_run.finished_at is not None
        assert (await _get_run(finished.id)).status is LlmRunStatus.succeeded


class TestWithoutBinaryContent:
    def test_leaves_other_messages_alone(self) -> None:
        messages: list[ModelMessage] = [
            ModelRequest(parts=[UserPromptPart(content="plain text")]),
            ModelResponse(parts=[TextPart(content="reply")]),
        ]

        assert without_binary_content(messages) == messages


class TestWebTools:
    def test_format_page_truncates_text_and_links(self) -> None:
        page = Page(
            url="https://example.com/",
            title="Example",
            text="x" * 50,
            links=tuple(
                Link(f"Link {i}", f"https://example.com/{i}") for i in range(5)
            ),
            structured_data=({"@type": "Restaurant", "name": "Saperavi"},),
        )

        formatted = format_page(
            page, max_chars=10, max_structured_data_chars=20, max_links=2
        )

        assert formatted == (
            "URL: https://example.com/\n\n"
            "Title: Example\n\n"
            "xxxxxxxxxx\n[truncated]\n\n"
            'Structured data:\n{"@type": "Restauran\n[truncated]\n\n'
            "Links:\n"
            "- Link 0: https://example.com/0\n"
            "- Link 1: https://example.com/1\n"
            "[3 more links]"
        )

    async def test_agent_fetches_page_with_browser(
        self, reset_database: None, browser_service: BrowserService, web_server_url: str
    ) -> None:
        agent = Agent(name="test.web", toolsets=[web_toolset])
        model = _fetch_then_echo(f"{web_server_url}/restaurant")

        with agent.override(model=model):
            result = await run_agent(agent, "Look up Saperavi", deps=None)

        assert "adjaruli khachapuri" in result.output
        assert '"servesCuisine": "Georgian"' in result.output
        run = await _get_run(result.run_id)
        assert run.requests == 2

    async def test_tool_reports_blocked_urls_to_the_model(
        self, reset_database: None, browser_service: BrowserService
    ) -> None:
        agent = Agent(name="test.web", toolsets=[web_toolset])

        with agent.override(model=_fetch_then_echo("file:///etc/passwd")):
            result = await run_agent(agent, "Read a file", deps=None)

        assert result.output.startswith("Could not open file:///etc/passwd")
