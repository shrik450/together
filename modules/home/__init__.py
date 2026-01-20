from litestar import Router

from .handlers import index

router = Router(
    path="/",
    route_handlers=[index],
)


def register() -> None:
    """Register home module. No models or schedules for now."""
    pass
