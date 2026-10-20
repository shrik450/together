from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from framework.json_value import JsonValue, parse_json


@dataclass(frozen=True, slots=True)
class Link:
    text: str
    url: str


@dataclass(frozen=True, slots=True)
class Page:
    url: str
    title: str
    text: str
    links: Sequence[Link]
    structured_data: Sequence[JsonValue]


def parse_json_ld(blocks: Sequence[str]) -> Sequence[JsonValue]:
    parsed: list[JsonValue] = []
    for block in blocks:
        try:
            parsed.append(parse_json(block))
        except ValidationError:
            continue
    return tuple(parsed)
