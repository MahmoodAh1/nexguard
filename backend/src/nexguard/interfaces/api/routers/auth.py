"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from nexguard.interfaces.api.deps import ContainerDep, CurrentUser, SessionDep
from nexguard.interfaces.api.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, request: Request, container: ContainerDep, session: SessionDep
) -> TokenResponse:
    pair = await container.authenticate(session).login(email=body.email, password=body.password)
    await container.audit(session).record(
        actor_id=None,
        action="login",
        resource=body.email,
        ip=request.client.host if request.client else None,
    )
    return TokenResponse.from_pair(pair)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest, container: ContainerDep, session: SessionDep
) -> TokenResponse:
    pair = await container.authenticate(session).refresh(refresh_token=body.refresh_token)
    return TokenResponse.from_pair(pair)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.from_entity(user)
