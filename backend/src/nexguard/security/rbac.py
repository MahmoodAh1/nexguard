"""Role-based access control (pure policy).

The pure authorization decision lives here so it can be unit-tested without any
web framework. The FastAPI dependency that enforces it (extracting the current
user, returning 401/403) is a thin wrapper in the interfaces layer.
"""

from __future__ import annotations

from nexguard.domain.entities import UserRole
from nexguard.domain.errors import AuthorizationError


def authorize(actor_role: UserRole, required_role: UserRole) -> None:
    """Raise :class:`AuthorizationError` if ``actor_role`` does not satisfy the requirement."""
    if not actor_role.satisfies(required_role):
        raise AuthorizationError(
            f"role '{actor_role.value}' does not satisfy required '{required_role.value}'"
        )


def is_authorized(actor_role: UserRole, required_role: UserRole) -> bool:
    return actor_role.satisfies(required_role)
