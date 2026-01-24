from collections.abc import Sequence

from litestar.plugins.sqlalchemy import SQLAlchemySyncConfig, SyncSessionConfig
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_registered_models: list[type[Base]] = []


def register_models(*models: type[Base]) -> None:
    for model in models:
        if not issubclass(model, Base):
            raise TypeError(
                f"Model '{model.__name__}' must inherit from framework Base"
            )
        if model not in _registered_models:
            _registered_models.append(model)


def get_registered_models() -> Sequence[type[Base]]:
    return _registered_models.copy()


db_config = SQLAlchemySyncConfig(
    connection_string="sqlite:///together.db",
    metadata=Base.metadata,
    create_all=False,
    session_config=SyncSessionConfig(expire_on_commit=False),
)
