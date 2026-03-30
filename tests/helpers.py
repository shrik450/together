from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_scheduler_task_calls: list[dict[str, Any]] = []


def reset_scheduler_task_calls() -> None:
    _scheduler_task_calls.clear()


def get_scheduler_task_calls() -> Sequence[Mapping[str, Any]]:
    return tuple(_scheduler_task_calls)


def scheduler_test_task(*args: object, **kwargs: object) -> dict[str, Any]:
    payload = {"args": tuple(args), "kwargs": dict(kwargs)}
    _scheduler_task_calls.append(payload)
    return payload


def scheduler_other_task(label: str = "other") -> str:
    _scheduler_task_calls.append({"args": (label,), "kwargs": {}})
    return label
