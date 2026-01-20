from litestar import get
from litestar.response import Template


@get("/")
async def index() -> Template:
    return Template(
        template_name="home/index.html",
    )
