from __future__ import annotations

from collections.abc import Mapping

from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from framework.auth.models import User
from framework.auth.state import (
    AuthenticatedUser,
    get_authenticated_user,
    get_auth_user_id,
)


async def provide_current_user(
    request: Request, db_session: AsyncSession
) -> User | None:
    user_id = get_auth_user_id(request)
    if user_id is None:
        return None
    return await db_session.get(User, user_id)


def get_current_user_template(
    context: Mapping[str, object],
) -> AuthenticatedUser | None:
    """Keep the template-context boundary typed before reading auth state."""

    request = context.get("request")
    if not isinstance(request, Request):
        return None
    return get_authenticated_user(request)
