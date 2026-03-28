from litestar import get
from litestar.response import Template

from framework.ui import NavNode


@get("/")
async def index() -> Template:
    return Template(
        template_name="home/index.html",
        context={
            "nav_stack": [
                [NavNode(label="Home", href="/")],
            ],
        },
    )
