from __future__ import annotations

"""Framework-owned scheduler boundary for Together.

This module keeps APScheduler 4.x confined behind a small framework API so the
rest of the app depends on stable framework concepts instead of alpha scheduler
internals. Code-level `ScheduleDefinition` objects are the source of truth for
the schedules the app intends to have, while APScheduler's SQLite tables hold
runtime state for durability across restarts.

The scheduler uses a dedicated SQLAlchemy engine against the same SQLite file as
the rest of the app. That keeps lifecycle ownership and infrastructure traffic
inside the scheduler layer without duplicating the shared SQLite PRAGMA setup
that already exists in `framework.db`.
"""

import inspect
import logging
import re
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler import AsyncScheduler, CoalescePolicy, ConflictPolicy, Schedule
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.cron import CronTrigger
from litestar import Litestar
from sqlalchemy.ext.asyncio import AsyncEngine

from framework.db import create_sqlite_async_engine, get_database_url

LOGGER = logging.getLogger("together.scheduler")
APSCHEDULER_LOGGER = LOGGER.getChild("runtime")
APSCHEDULER_LOGGER.setLevel(logging.WARNING)
_STATE_KEY = "scheduler_service"
_APP_METADATA_KEY = "together_app_managed"
_APP_METADATA_VALUE = "framework.scheduler"
_DEFAULT_MISFIRE_GRACE_TIME = timedelta(minutes=15)
_CRON_REPR_PATTERN = re.compile(
    r"^CronTrigger\(year='(?P<year>[^']*)', month='(?P<month>[^']*)', day='(?P<day>[^']*)', "
    r"week='(?P<week>[^']*)', day_of_week='(?P<day_of_week>[^']*)', hour='(?P<hour>[^']*)', "
    r"minute='(?P<minute>[^']*)', second='(?P<second>[^']*)', start_time='[^']*', timezone='(?P<timezone>[^']*)'"
    r"(?:, end_time='[^']*')?\)$"
)


@dataclass(frozen=True, slots=True)
class ScheduleRef:
    id: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ScheduleRef.id must not be empty")


class CoalesceMode(StrEnum):
    earliest = "earliest"
    latest = "latest"
    all = "all"


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    ref: ScheduleRef
    func: Callable[..., object]
    cron: str
    timezone: str = "UTC"
    args: Sequence[object] = field(default_factory=tuple)
    kwargs: Mapping[str, object] = field(default_factory=dict)
    paused: bool = False
    coalesce: CoalesceMode = CoalesceMode.latest
    misfire_grace_time: timedelta | None = _DEFAULT_MISFIRE_GRACE_TIME

    def __post_init__(self) -> None:
        if not self.cron.strip():
            raise ValueError("ScheduleDefinition.cron must not be empty")
        if not self.timezone.strip():
            raise ValueError("ScheduleDefinition.timezone must not be empty")
        if (
            self.misfire_grace_time is not None
            and self.misfire_grace_time <= timedelta()
        ):
            raise ValueError("misfire_grace_time must be positive when provided")

        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "kwargs", MappingProxyType(dict(self.kwargs)))


@dataclass(frozen=True, slots=True)
class ScheduleInfo:
    ref: ScheduleRef
    cron: str
    timezone: str
    paused: bool
    coalesce: CoalesceMode
    next_fire_time: datetime | None
    last_fire_time: datetime | None


class SchedulerService:
    def __init__(
        self,
        *,
        scheduler: AsyncScheduler,
        definitions: Mapping[str, ScheduleDefinition],
        logger: logging.Logger,
    ) -> None:
        self._scheduler = scheduler
        self._definitions = definitions
        self._logger = logger

    async def list_schedules(self) -> Sequence[ScheduleInfo]:
        live_schedules = {
            schedule.id: schedule for schedule in await self._scheduler.get_schedules()
        }
        schedule_infos: list[ScheduleInfo] = []

        for definition in self._definitions.values():
            live_schedule = live_schedules.get(definition.ref.id)
            schedule_infos.append(
                ScheduleInfo(
                    ref=definition.ref,
                    cron=definition.cron,
                    timezone=definition.timezone,
                    paused=live_schedule.paused if live_schedule else definition.paused,
                    coalesce=definition.coalesce,
                    next_fire_time=_normalize_datetime(
                        live_schedule.next_fire_time if live_schedule else None
                    ),
                    last_fire_time=_normalize_datetime(
                        live_schedule.last_fire_time if live_schedule else None
                    ),
                )
            )

        return tuple(sorted(schedule_infos, key=lambda item: item.ref.id))

    async def run_now(
        self,
        ref: ScheduleRef,
        *,
        args: Sequence[object] | None = None,
        kwargs: Mapping[str, object] | None = None,
    ) -> Any:
        definition = self._definitions.get(ref.id)
        if definition is None:
            raise ValueError(f"Unknown schedule ref: {ref.id}")

        job_args = tuple(definition.args if args is None else args)
        job_kwargs = dict(definition.kwargs if kwargs is None else kwargs)

        self._logger.info("Running schedule manually", extra={"schedule_id": ref.id})
        return await self._scheduler.run_job(
            definition.func,
            args=job_args,
            kwargs=job_kwargs,
            metadata=_app_metadata(ref),
        )


_registry: dict[str, ScheduleDefinition] = {}


def add_schedule(definition: ScheduleDefinition) -> ScheduleRef:
    _validate_schedule_definition(definition)
    if definition.ref.id in _registry:
        LOGGER.warning(
            "Rejected duplicate schedule registration",
            extra={"schedule_id": definition.ref.id},
        )
        raise ValueError(f"Duplicate schedule ref: {definition.ref.id}")

    _registry[definition.ref.id] = definition
    return definition.ref


def get_scheduler_service(app_or_scope: Any) -> SchedulerService:
    state = getattr(app_or_scope, "state", None)
    if state is None:
        app = getattr(app_or_scope, "app", None)
        state = getattr(app, "state", None)

    service = getattr(state, _STATE_KEY, None)
    if service is None:
        raise RuntimeError("Scheduler service is not available")
    return service


@asynccontextmanager
async def scheduler_lifespan(app: Litestar) -> AsyncIterator[None]:
    """Own the scheduler lifecycle for the whole application.

    The scheduler gets its own engine against the same SQLite file so it can
    keep APScheduler's operational traffic separate from request-scoped ORM
    work while still reusing the shared SQLite configuration from `framework.db`.
    """

    scheduler_engine = _create_scheduler_engine()
    # APScheduler owns its operational tables directly so Alembic stays focused
    # on app/domain schema while scheduler runtime state remains an implementation detail.
    data_store = SQLAlchemyDataStore(scheduler_engine)
    scheduler = AsyncScheduler(data_store=data_store, logger=APSCHEDULER_LOGGER)

    LOGGER.info("Starting scheduler")
    try:
        async with scheduler:
            definitions = _registered_definitions()
            await _reconcile_schedules(scheduler, definitions)
            await scheduler.start_in_background()

            setattr(
                app.state,
                _STATE_KEY,
                SchedulerService(
                    scheduler=scheduler,
                    definitions=definitions,
                    logger=LOGGER,
                ),
            )
            LOGGER.info("Scheduler started")
            try:
                yield
            finally:
                if hasattr(app.state, _STATE_KEY):
                    delattr(app.state, _STATE_KEY)
                LOGGER.info("Stopping scheduler")
    finally:
        await scheduler_engine.dispose()
        LOGGER.info("Scheduler stopped")


def _create_scheduler_engine() -> AsyncEngine:
    return create_sqlite_async_engine(
        get_database_url(),
        connect_args={"autocommit": False},
    )


def _registered_definitions() -> Mapping[str, ScheduleDefinition]:
    return MappingProxyType(dict(_registry))


async def _reconcile_schedules(
    scheduler: AsyncScheduler,
    definitions: Mapping[str, ScheduleDefinition],
) -> None:
    """Reconcile framework-defined schedules into the live scheduler state.

    Framework definitions are authoritative for Stage 2. APScheduler's tables
    provide runtime durability, but startup still adds missing schedules,
    reapplies desired definitions, and removes stale app-managed schedules.
    """

    live_schedules = {
        schedule.id: schedule for schedule in await scheduler.get_schedules()
    }

    for schedule in live_schedules.values():
        if schedule.id in definitions:
            continue
        if not _is_app_managed_schedule(schedule):
            continue

        LOGGER.info("Removing stale schedule", extra={"schedule_id": schedule.id})
        await scheduler.remove_schedule(schedule.id)

    for definition in definitions.values():
        live_schedule = live_schedules.get(definition.ref.id)
        if live_schedule is None:
            LOGGER.info(
                "Registering schedule", extra={"schedule_id": definition.ref.id}
            )
        elif _schedule_matches_definition(live_schedule, definition):
            LOGGER.info(
                "Schedule already up to date",
                extra={"schedule_id": definition.ref.id},
            )
            continue
        else:
            LOGGER.info("Updating schedule", extra={"schedule_id": definition.ref.id})

        await scheduler.add_schedule(
            definition.func,
            _build_cron_trigger(definition.cron, definition.timezone),
            id=definition.ref.id,
            args=definition.args,
            kwargs=definition.kwargs,
            paused=definition.paused,
            coalesce=_to_apscheduler_coalesce(definition.coalesce),
            misfire_grace_time=definition.misfire_grace_time,
            metadata=_app_metadata(definition.ref),
            conflict_policy=ConflictPolicy.replace,
        )


def _validate_schedule_definition(definition: ScheduleDefinition) -> None:
    _validate_callable(definition.func)
    _validate_timezone(definition.timezone)

    try:
        _build_cron_trigger(definition.cron, definition.timezone)
    except Exception as exc:
        LOGGER.warning(
            "Rejected invalid schedule definition",
            extra={"schedule_id": definition.ref.id},
        )
        raise ValueError(
            f"Invalid cron expression for schedule {definition.ref.id}: {definition.cron}"
        ) from exc


def _validate_callable(func: Any) -> None:
    if inspect.ismethod(func) or not inspect.isfunction(func):
        raise ValueError("Scheduled callables must be module-level functions")
    if func.__name__ == "<lambda>":
        raise ValueError("Scheduled callables must not be lambdas")
    if func.__qualname__ != func.__name__:
        raise ValueError(
            "Scheduled callables must be importable module-level functions without closures"
        )

    module = inspect.getmodule(func)
    if module is None or getattr(module, func.__name__, None) is not func:
        raise ValueError("Scheduled callables must be importable from their module")


def _validate_timezone(timezone_name: str) -> None:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {timezone_name}") from exc


def _build_cron_trigger(cron: str, timezone_name: str) -> CronTrigger:
    minute, hour, day, month, day_of_week = _parse_cron(cron)
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        second=0,
        timezone=timezone_name,
    )


def _parse_cron(cron: str) -> tuple[str, str, str, str, str]:
    parts = cron.split()
    if len(parts) != 5:
        raise ValueError("Cron expressions must use standard 5-field crontab syntax")
    minute, hour, day, month, day_of_week = parts
    return minute, hour, day, month, day_of_week


def _to_apscheduler_coalesce(mode: CoalesceMode) -> CoalescePolicy:
    return {
        CoalesceMode.earliest: CoalescePolicy.earliest,
        CoalesceMode.latest: CoalescePolicy.latest,
        CoalesceMode.all: CoalescePolicy.all,
    }[mode]


def _app_metadata(ref: ScheduleRef) -> dict[str, str]:
    return {
        _APP_METADATA_KEY: _APP_METADATA_VALUE,
        "schedule_id": ref.id,
    }


def _is_app_managed_schedule(schedule: Schedule) -> bool:
    return schedule.metadata.get(_APP_METADATA_KEY) == _APP_METADATA_VALUE


def _schedule_matches_definition(
    schedule: Schedule,
    definition: ScheduleDefinition,
) -> bool:
    trigger_signature = _cron_trigger_signature(schedule.trigger)
    if trigger_signature is None:
        return False

    minute, hour, day, month, day_of_week = _parse_cron(definition.cron)

    return (
        schedule.task_id == _task_id(definition.func)
        and trigger_signature
        == {
            "year": "*",
            "month": month,
            "day": day,
            "week": "*",
            "day_of_week": day_of_week,
            "hour": hour,
            "minute": minute,
            "second": "0",
            "timezone": definition.timezone,
        }
        and tuple(schedule.args) == tuple(definition.args)
        and dict(schedule.kwargs) == dict(definition.kwargs)
        and schedule.paused is definition.paused
        and schedule.coalesce == _to_apscheduler_coalesce(definition.coalesce)
        and schedule.misfire_grace_time == definition.misfire_grace_time
        and dict(schedule.metadata) == _app_metadata(definition.ref)
    )


def _task_id(func: Callable[..., object]) -> str:
    return f"{func.__module__}:{func.__qualname__}"


def _cron_trigger_signature(trigger: object) -> dict[str, str] | None:
    # APScheduler 4.x alpha currently gives us CronTrigger reprs that stay
    # stable across datastore round-trips even when direct field access does not.
    # TODO: Replace repr parsing with direct field access once APScheduler 4.x
    # stabilises. If the repr format changes this silently returns None, causing
    # every schedule to be replaced on startup (safe but noisy).
    match = _CRON_REPR_PATTERN.match(str(trigger))
    if match is None:
        return None
    return match.groupdict()


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
