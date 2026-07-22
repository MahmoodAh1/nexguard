"""Health and readiness."""

from __future__ import annotations

from fastapi import APIRouter

from nexguard import __version__
from nexguard.interfaces.api.deps import ContainerDep
from nexguard.interfaces.api.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health(container: ContainerDep) -> HealthOut:
    return HealthOut(
        status="ok",
        version=__version__,
        environment=container.settings.env,
        detectors_loaded=container.detectors is not None,
        llm_provider=container.settings.llm_provider,
        event_bus=container.settings.event_bus,
    )
