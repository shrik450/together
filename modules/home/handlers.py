from litestar import get
from litestar.response import Template

from framework.ui import NavNode


@get("/")
async def index() -> Template:
    return Template(
        template_name="home/index.html",
        context={
            # The root page is the special case: it provides the Home level
            # itself because there is no enclosing module node.
            "nav_stack": [
                [NavNode(label="Home", href="/")],
            ],
        },
    )
