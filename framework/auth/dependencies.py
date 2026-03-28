from __future__ import annotations

from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from framework.auth.models import User
from framework.auth.middleware import AuthenticatedUser


async def provide_current_user(
    request: Request, db_session: AsyncSession
) -> User | None:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        return None
    return await db_session.get(User, user_id)


def get_current_user_template(context: dict) -> AuthenticatedUser | None:
    request = context.get("request")
    if request is None:
        return None
    return getattr(request.state, "current_user", None)
