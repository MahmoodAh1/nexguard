"""FastAPI dependencies: composition-root access, sessions, auth, and RBAC.

These are the thin glue between HTTP and the application layer. The pure
authorization decision lives in ``security.rbac``; here it is enforced by
extracting the caller and returning the right HTTP status on failure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from nexguard.domain.entities import User, UserRole
from nexguard.domain.errors import AuthenticationError
from nexguard.interfaces.api.container import Container
from nexguard.security.rbac import authorize

_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - misconfiguration guard
        raise RuntimeError("application container is not initialized")
    assert isinstance(container, Container)
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.database.session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    container: ContainerDep,
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if credentials is None:
        raise AuthenticationError("missing bearer token")
    claims = container.tokens.decode(credentials.credentials)
    if claims.token_type != "access":
        raise AuthenticationError("an access token is required")
    try:
        user_id = UUID(claims.subject)
    except ValueError as exc:
        raise AuthenticationError("malformed token subject") from exc
    user = await container.users(session).get(user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("user not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: UserRole) -> Callable[[User], User]:
    def dependency(user: CurrentUser) -> User:
        authorize(user.role, role)
        return user

    return dependency


ViewerUser = Annotated[User, Depends(require_role(UserRole.VIEWER))]
AnalystUser = Annotated[User, Depends(require_role(UserRole.ANALYST))]
AdminUser = Annotated[User, Depends(require_role(UserRole.ADMIN))]
