from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore

import framework.scheduler.service as scheduler_service_module
from framework.scheduler import (
    CoalesceMode,
    ScheduleDefinition,
    ScheduleRef,
    add_schedule,
    get_scheduler_service,
    scheduler_lifespan,
)
from tests.helpers import (
    get_scheduler_task_calls,
    scheduler_other_task,
    scheduler_test_task,
)


@pytest.fixture
def scheduler_database_url(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'scheduler.db'}"
    monkeypatch.setenv("TOGETHER_DATABASE_URL", database_url)
    return database_url


class TestScheduleDefinitionValidation:
    @pytest.mark.parametrize("value", ["", "   "])
    def test_schedule_ref_rejects_blank_ids(self, value: str) -> None:
        with pytest.raises(ValueError, match="ScheduleRef.id must not be empty"):
            ScheduleRef(value)

    @pytest.mark.parametrize(
        ("cron", "timezone", "misfire_grace_time", "message"),
        [
            (
                "",
                "UTC",
                timedelta(minutes=1),
                "ScheduleDefinition.cron must not be empty",
            ),
            (
                "0 7 * * *",
                "",
                timedelta(minutes=1),
                "ScheduleDefinition.timezone must not be empty",
            ),
            ("0 7 * * *", "UTC", timedelta(), "misfire_grace_time must be positive"),
        ],
    )
    def test_schedule_definition_rejects_invalid_basic_fields(
        self,
        cron: str,
        timezone: str,
        misfire_grace_time: timedelta,
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=message):
            ScheduleDefinition(
                ref=ScheduleRef("job"),
                func=scheduler_test_task,
                cron=cron,
                timezone=timezone,
                misfire_grace_time=misfire_grace_time,
            )

    @pytest.mark.parametrize("cron", ["0 7 * *", "0 7 * * * *"])
    def test_rejects_invalid_cron(self, cron: str) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=scheduler_test_task,
            cron=cron,
        )

        with pytest.raises(ValueError, match="Invalid cron expression"):
            add_schedule(definition)

    @pytest.mark.parametrize("timezone", ["Mars/Phobos", "Not/AZone"])
    def test_rejects_invalid_timezones(self, timezone: str) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=scheduler_test_task,
            cron="0 7 * * *",
            timezone=timezone,
        )

        with pytest.raises(ValueError, match="Unknown timezone"):
            add_schedule(definition)

    def test_freezes_args_and_kwargs(self) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=scheduler_test_task,
            cron="0 7 * * *",
            args=[1, 2],
            kwargs={"foo": "bar"},
        )

        assert definition.args == (1, 2)
        assert dict(definition.kwargs) == {"foo": "bar"}
        with pytest.raises(TypeError):
            definition.kwargs["foo"] = "baz"  # type: ignore[index]

    def test_rejects_lambda_callable(self) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=lambda: None,
            cron="0 7 * * *",
        )

        with pytest.raises(ValueError, match="must not be lambdas"):
            add_schedule(definition)

    def test_rejects_nested_callable(self) -> None:
        def outer():
            def inner() -> None:
                return None

            return inner

        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=outer(),
            cron="0 7 * * *",
        )

        with pytest.raises(ValueError, match="without closures"):
            add_schedule(definition)

    def test_rejects_bound_method_callable(self) -> None:
        class Example:
            def task(self) -> None:
                return None

        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=Example().task,
            cron="0 7 * * *",
        )

        with pytest.raises(ValueError, match="module-level functions"):
            add_schedule(definition)


class TestScheduleRegistration:
    def test_rejects_duplicate_schedule_refs(self) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("job"),
            func=scheduler_test_task,
            cron="0 7 * * *",
        )

        add_schedule(definition)

        with pytest.raises(ValueError, match="Duplicate schedule ref"):
            add_schedule(definition)


class TestSchedulerLifespan:
    async def _get_raw_schedules(self, database_url: str):
        data_store = SQLAlchemyDataStore(database_url)
        async with AsyncScheduler(data_store=data_store) as scheduler:
            try:
                return await scheduler.get_schedules()
            finally:
                await scheduler.stop()
                await scheduler.wait_until_stopped()

    async def _seed_schedule(
        self,
        database_url: str,
        *,
        schedule_id: str,
        func,
        cron: str = "0 7 * * *",
        args: tuple[object, ...] = (),
        metadata: dict[str, str] | None = None,
    ) -> None:
        data_store = SQLAlchemyDataStore(database_url)
        async with AsyncScheduler(data_store=data_store) as scheduler:
            try:
                minute, hour, day, month, day_of_week = cron.split()
                from apscheduler import ConflictPolicy
                from apscheduler.triggers.cron import CronTrigger

                await scheduler.add_schedule(
                    func,
                    CronTrigger(
                        minute=minute,
                        hour=hour,
                        day=day,
                        month=month,
                        day_of_week=day_of_week,
                        second=0,
                        timezone="UTC",
                    ),
                    id=schedule_id,
                    args=args,
                    metadata={} if metadata is None else metadata,
                    conflict_policy=ConflictPolicy.replace,
                )
            finally:
                await scheduler.stop()
                await scheduler.wait_until_stopped()

    async def test_attaches_and_removes_scheduler_service(
        self, litestar_app, scheduler_database_url: str
    ) -> None:
        async with scheduler_lifespan(litestar_app):
            service = get_scheduler_service(litestar_app)
            assert service is not None

        with pytest.raises(RuntimeError, match="Scheduler service is not available"):
            get_scheduler_service(litestar_app)

    async def test_reconciles_registered_schedules_on_startup(
        self, litestar_app, scheduler_database_url: str
    ) -> None:
        add_schedule(
            ScheduleDefinition(
                ref=ScheduleRef("morning-job"),
                func=scheduler_test_task,
                cron="0 7 * * *",
            )
        )

        async with scheduler_lifespan(litestar_app):
            schedules = await self._get_raw_schedules(scheduler_database_url)

        assert [schedule.id for schedule in schedules] == ["morning-job"]

    async def test_restarting_lifespan_does_not_duplicate_schedules(
        self, litestar_app, scheduler_database_url: str
    ) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("singleton-job"),
            func=scheduler_test_task,
            cron="0 7 * * *",
        )
        add_schedule(definition)

        async with scheduler_lifespan(litestar_app):
            pass
        async with scheduler_lifespan(litestar_app):
            schedules = await self._get_raw_schedules(scheduler_database_url)

        assert [schedule.id for schedule in schedules] == ["singleton-job"]

    async def test_replaces_changed_schedule_definition_on_restart(
        self, litestar_app, scheduler_database_url: str
    ) -> None:
        add_schedule(
            ScheduleDefinition(
                ref=ScheduleRef("replace-job"),
                func=scheduler_test_task,
                cron="0 7 * * *",
                args=("old",),
            )
        )

        async with scheduler_lifespan(litestar_app):
            pass

        scheduler_service_module._registry.clear()
        add_schedule(
            ScheduleDefinition(
                ref=ScheduleRef("replace-job"),
                func=scheduler_test_task,
                cron="15 8 * * *",
                args=("new",),
            )
        )

        async with scheduler_lifespan(litestar_app):
            schedules = await self._get_raw_schedules(scheduler_database_url)

        assert len(schedules) == 1
        assert tuple(schedules[0].args) == ("new",)
        assert "minute='15'" in str(schedules[0].trigger)

    async def test_removes_stale_app_managed_schedules(
        self, litestar_app, scheduler_database_url: str
    ) -> None:
        await self._seed_schedule(
            scheduler_database_url,
            schedule_id="stale-job",
            func=scheduler_other_task,
            metadata={
                "together_app_managed": "framework.scheduler",
                "schedule_id": "stale-job",
            },
        )

        async with scheduler_lifespan(litestar_app):
            schedules = await self._get_raw_schedules(scheduler_database_url)

        assert schedules == []


class TestSchedulerRuntime:
    async def test_run_now_executes_registered_function(self, litestar_app) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("manual-job"),
            func=scheduler_test_task,
            cron="0 7 * * *",
            args=("hello",),
            kwargs={"answer": 42},
        )
        add_schedule(definition)

        async with scheduler_lifespan(litestar_app):
            service = get_scheduler_service(litestar_app)
            result = await service.run_now(definition.ref)

        assert result == {"args": ("hello",), "kwargs": {"answer": 42}}
        assert list(get_scheduler_task_calls()) == [result]

    async def test_run_now_allows_overriding_args_and_kwargs(
        self, litestar_app
    ) -> None:
        definition = ScheduleDefinition(
            ref=ScheduleRef("manual-job"),
            func=scheduler_test_task,
            cron="0 7 * * *",
            args=("hello",),
            kwargs={"answer": 42},
        )
        add_schedule(definition)

        async with scheduler_lifespan(litestar_app):
            service = get_scheduler_service(litestar_app)
            result = await service.run_now(
                definition.ref,
                args=("override",),
                kwargs={"answer": 7},
            )

        assert result == {"args": ("override",), "kwargs": {"answer": 7}}

    async def test_run_now_rejects_unknown_schedule_ref(self, litestar_app) -> None:
        async with scheduler_lifespan(litestar_app):
            service = get_scheduler_service(litestar_app)
            with pytest.raises(ValueError, match="Unknown schedule ref"):
                await service.run_now(ScheduleRef("missing-job"))


class TestSchedulerService:
    async def test_get_scheduler_service_reads_scope_state(self, litestar_app) -> None:
        async with scheduler_lifespan(litestar_app):
            direct_service = get_scheduler_service(litestar_app)
            scope = SimpleNamespace(app=litestar_app)

            assert get_scheduler_service(scope) is direct_service

    async def test_list_schedules_returns_sorted_infos(self, litestar_app) -> None:
        add_schedule(
            ScheduleDefinition(
                ref=ScheduleRef("b-job"),
                func=scheduler_test_task,
                cron="0 7 * * *",
            )
        )
        add_schedule(
            ScheduleDefinition(
                ref=ScheduleRef("a-job"),
                func=scheduler_test_task,
                cron="30 8 * * *",
                paused=True,
                coalesce=CoalesceMode.earliest,
            )
        )

        async with scheduler_lifespan(litestar_app):
            service = get_scheduler_service(litestar_app)
            schedules = await service.list_schedules()

        assert [schedule.ref.id for schedule in schedules] == ["a-job", "b-job"]
        assert schedules[0].paused is True
        assert schedules[0].coalesce == CoalesceMode.earliest
        assert schedules[0].next_fire_time is not None
