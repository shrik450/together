from litestar.plugins.sqlalchemy import SQLAlchemySyncConfig
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db_config = SQLAlchemySyncConfig(
    connection_string="sqlite:///together.db",
    metadata=Base.metadata,
    create_all=True,
)
