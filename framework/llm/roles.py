import os
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class ModelRole(StrEnum):
    default = "default"
    fast = "fast"


_DEFAULT_MODELS: Mapping[ModelRole, str] = MappingProxyType(
    {
        ModelRole.default: "anthropic:claude-opus-5-5",
        ModelRole.fast: "anthropic:claude-haiku-5-5",
    }
)


def resolve_model(role: ModelRole) -> str:
    """Return the Pydantic AI model name for a role.

    `TOGETHER_LLM_MODEL_<ROLE>` overrides the default with any
    `<provider>:<model>` name Pydantic AI accepts.
    """
    return os.getenv(f"TOGETHER_LLM_MODEL_{role.name.upper()}") or _DEFAULT_MODELS[role]
