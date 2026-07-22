"""Authentication use cases: create users and log in."""

from __future__ import annotations

from nexguard.domain.auth import TokenPair
from nexguard.domain.entities import User, UserRole
from nexguard.domain.errors import AuthenticationError, ValidationError
from nexguard.domain.ports import PasswordHasher, TokenService, UserRepository


class CreateUser:
    """Create a user with a hashed password (used by seeding and admin flows)."""

    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def execute(self, *, email: str, password: str, role: UserRole) -> User:
        normalized = email.strip().lower()
        if not normalized or "@" not in normalized:
            raise ValidationError("a valid email is required")
        if len(password) < 8:
            raise ValidationError("password must be at least 8 characters")
        if await self._users.by_email(normalized) is not None:
            raise ValidationError(f"user already exists: {normalized}")
        user = User(
            email=normalized, password_hash=self._hasher.hash(password), role=role
        )
        return await self._users.add(user)


class Authenticate:
    """Verify credentials and issue a token pair."""

    def __init__(
        self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._tokens = tokens

    async def login(self, *, email: str, password: str) -> TokenPair:
        user = await self._users.by_email(email.strip().lower())
        # Verify a hash even when the user is missing to blunt timing-based
        # user enumeration; the decision is identical either way.
        password_hash = user.password_hash if user else _DUMMY_HASH
        password_ok = self._hasher.verify(password, password_hash)
        if user is None or not user.is_active or not password_ok:
            raise AuthenticationError("invalid email or password")
        return self._tokens.issue(user)


# A precomputed Argon2id hash of a random value, used only to equalize timing.
_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "c29tZS1zdGF0aWMtc2FsdA$b3JzZW1vLW5vdC1hLXJlYWwtcGFzc3dvcmQtaGFzaA"
)
