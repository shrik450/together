from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from advanced_alchemy.types import DateTimeUTC
from sqlalchemy import JSON, Enum, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from framework.db import Base


class LlmRunStatus(StrEnum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


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
    messages: Mapped[list[object] | None] = mapped_column(JSON)
