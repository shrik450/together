from litestar import get
from litestar.response import Template


@get("/", sync_to_thread=False)
def index() -> Template:
    return Template(
        template_name="home/index.html",
    )
