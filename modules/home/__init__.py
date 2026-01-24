from pathlib import Path

from litestar import Router

from framework import register_template_dirs

from .handlers import index

router = Router(
    path="/",
    route_handlers=[index],
)


def register() -> None:
    register_template_dirs(Path(__file__).parent / "templates")
