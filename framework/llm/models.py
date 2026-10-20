from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import override

from advanced_alchemy.types import DateTimeUTC
from pydantic_ai import ModelMessage, ModelMessagesTypeAdapter
from sqlalchemy import JSON, Dialect, Enum, Numeric, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from framework.db import Base
from framework.json_value import JsonValue, parse_json


class LlmRunStatus(StrEnum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    interrupted = "interrupted"


class ModelMessagesJSON(TypeDecorator[list[ModelMessage]]):
    """Stores Pydantic AI messages as JSON and parses them back on load."""

    impl = JSON
    cache_ok = True

    @override
    def process_bind_param(
        self, value: list[ModelMessage] | None, dialect: Dialect
    ) -> JsonValue:
        if value is None:
            return None
        return parse_json(ModelMessagesTypeAdapter.dump_json(value))

    @override
    def process_result_value(
        self, value: object, dialect: Dialect
    ) -> list[ModelMessage] | None:
        if value is None:
            return None
        return ModelMessagesTypeAdapter.validate_python(value)


class LlmRun(Base):
    __tablename__ = "llm_runs"

    agent: Mapped[str]
    model: Mapped[str]
    status: Mapped[LlmRunStatus] = mapped_column(
        Enum(LlmRunStatus, native_enum=False, length=16)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTimeUTC(timezone=True))
    requests: Mapped[int] = mapped_column(default=0)
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    error: Mapped[str | None]
    # The full conversation, so a later run can continue from it.
    messages: Mapped[list[ModelMessage] | None] = mapped_column(ModelMessagesJSON)
