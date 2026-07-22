"""Log Explorer endpoints: sessions, session detail, and mined templates."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from nexguard.domain.errors import NotFoundError
from nexguard.interfaces.api.deps import ContainerDep, SessionDep, ViewerUser
from nexguard.interfaces.api.schemas import (
    SessionDetailOut,
    SessionSummaryOut,
    TemplateOut,
)

router = APIRouter(prefix="/api/v1", tags=["logs"])


@router.get("/sessions", response_model=list[SessionSummaryOut])
async def list_sessions(
    _user: ViewerUser,
    container: ContainerDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SessionSummaryOut]:
    sessions = await container.logs(session).list_sessions(limit=limit, offset=offset)
    return [SessionSummaryOut.from_entity(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: UUID, _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> SessionDetailOut:
    found = await container.logs(session).get_session(session_id)
    if found is None:
        raise NotFoundError("Session", session_id)
    return SessionDetailOut.from_entity(found)


@router.get("/templates", response_model=list[TemplateOut])
async def list_templates(
    _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> list[TemplateOut]:
    templates = await container.templates(session).all()
    return [TemplateOut.from_entity(t) for t in templates]
