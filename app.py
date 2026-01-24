from pathlib import Path

from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.plugins.htmx import HTMXPlugin
from litestar.plugins.sqlalchemy import SQLAlchemyPlugin
from litestar.static_files import create_static_files_router
from litestar.template.config import TemplateConfig

from framework import get_template_dirs
from framework.db import db_config
from modules import home

home.register()


app = Litestar(
    route_handlers=[
        home.router,
        create_static_files_router(path="/static", directories=[Path("static")]),
    ],
    plugins=[
        SQLAlchemyPlugin(config=db_config),
        HTMXPlugin(),
    ],
    template_config=TemplateConfig(
        directory=get_template_dirs(),
        engine=JinjaTemplateEngine,
    ),
)
