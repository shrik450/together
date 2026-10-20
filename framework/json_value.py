from pydantic import RootModel

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)


class _Json(RootModel[JsonValue]):
    pass


def parse_json(text: str | bytes) -> JsonValue:
    """Parse JSON into `JsonValue`; raises pydantic's `ValidationError`."""
    return _Json.model_validate_json(text).root
