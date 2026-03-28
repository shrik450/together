from __future__ import annotations

from framework.auth.dependencies import get_current_user_template, provide_current_user
from framework.auth.guards import require_auth
from framework.auth.handlers import auth_router
from framework.auth.models import User


__all__ = [
    "User",
    "auth_router",
    "get_current_user_template",
    "provide_current_user",
    "require_auth",
]
