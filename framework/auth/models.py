from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Mapped, mapped_column

from framework.db import Base

_password_hasher = PasswordHasher()


class User(Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]

    def verify_password(self, password: str) -> bool:
        try:
            return _password_hasher.verify(self.password_hash, password)
        except VerifyMismatchError:
            return False

    @staticmethod
    def hash_password(password: str) -> str:
        return _password_hasher.hash(password)
