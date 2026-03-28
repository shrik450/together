from pathlib import Path

from advanced_alchemy.extensions.litestar import SQLAlchemyInitPlugin
from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.middleware import DefineMiddleware
from litestar.plugins.htmx import HTMXPlugin
from litestar.static_files import create_static_files_router
from litestar.template.config import TemplateConfig

from framework import get_template_dirs
from framework.auth import (
    auth_router,
    get_current_user_template,
    provide_current_user,
    require_auth,
)
from framework.auth.guards import AuthRequired, auth_required_handler
from framework.db import create_db_config
from framework.security import SecurityHeadersMiddleware
from framework.auth.middleware import SessionMiddleware
from framework.ui import NavNode, get_nav_nodes
from modules import home

home.register()

db_config = create_db_config()


def register_template_callables(engine: JinjaTemplateEngine) -> None:
    engine.register_template_callable(
        key="get_nav_nodes",
        template_callable=lambda _ctx: get_nav_nodes(),
    )
    engine.register_template_callable(
        key="get_current_user",
        template_callable=get_current_user_template,
    )
    engine.register_template_callable(
        key="home_node",
        template_callable=lambda _ctx: NavNode(label="Home", href="/"),
    )


app = Litestar(
    route_handlers=[
        home.router,
        auth_router,
        create_static_files_router(path="/static", directories=[Path("static")]),
    ],
    guards=[require_auth],
    exception_handlers={AuthRequired: auth_required_handler},
    middleware=[
        DefineMiddleware(SecurityHeadersMiddleware),
        DefineMiddleware(SessionMiddleware),
    ],
    plugins=[
        SQLAlchemyInitPlugin(config=db_config),
        HTMXPlugin(),
    ],
    dependencies={"current_user": provide_current_user},
    template_config=TemplateConfig(
        directory=get_template_dirs(),
        engine=JinjaTemplateEngine,
        engine_callback=register_template_callables,
    ),
)
