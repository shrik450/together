from __future__ import annotations

from litestar import Request, Router, get, post
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from framework.auth.models import User
from framework.auth.session import (
    create_session_cookie,
    get_session_config,
    normalize_next_url,
)


def _set_session_cookie(response: Redirect, user_id: int) -> None:
    config = get_session_config()
    token = create_session_cookie(user_id, config)
    response.set_cookie(
        key=config.cookie_name,
        value=token,
        max_age=config.max_age_seconds,
        httponly=True,
        secure=config.secure_cookies,
        samesite=config.same_site,
        path="/",
    )


def _clear_session_cookie(response: Redirect) -> None:
    config = get_session_config()
    response.delete_cookie(
        key=config.cookie_name,
        path="/",
        secure=config.secure_cookies,
        samesite=config.same_site,
    )


@get("/login")
async def login_page(request: Request) -> Template | Redirect:
    next_url = normalize_next_url(request.query_params.get("next"))
    if getattr(request.state, "user_id", None) is not None:
        return Redirect(next_url)
    return Template(
        template_name="auth/login.html",
        context={"error": None, "next": next_url, "username": ""},
    )


@post("/login")
async def login_submit(
    request: Request, db_session: AsyncSession
) -> Template | Redirect:
    form = await request.form()
    username = str(form.get("username") or "").strip()
    password = str(form.get("password") or "")
    next_url = normalize_next_url(str(form.get("next") or ""))

    user = (
        await db_session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()

    if user is not None and user.verify_password(password):
        response = Redirect(next_url)
        _set_session_cookie(response, user.id)
        return response

    return Template(
        template_name="auth/login.html",
        context={
            "error": "Invalid username or password",
            "next": next_url,
            "username": username,
        },
    )


@post("/logout")
async def logout() -> Redirect:
    response = Redirect("/auth/login")
    _clear_session_cookie(response)
    return response


auth_router = Router(path="/auth", route_handlers=[login_page, login_submit, logout])
