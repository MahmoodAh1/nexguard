"""Configuration: read + (admin) update the runtime detection operating point."""

from __future__ import annotations

from fastapi import APIRouter, Request

from nexguard.interfaces.api.deps import AdminUser, ContainerDep, SessionDep, ViewerUser
from nexguard.interfaces.api.schemas import ConfigOut, ConfigUpdateRequest

router = APIRouter(prefix="/api/v1/config", tags=["configuration"])


def _current(container: ContainerDep) -> ConfigOut:
    runtime = container.runtime
    return ConfigOut(
        seq_weight=runtime.seq_weight,
        stat_weight=runtime.stat_weight,
        threshold=runtime.threshold,
        detectors_loaded=container.detectors is not None,
        llm_provider=container.settings.llm_provider,
        model_name=container.model_name,
    )


@router.get("", response_model=ConfigOut)
async def get_config(_user: ViewerUser, container: ContainerDep) -> ConfigOut:
    return _current(container)


@router.put("", response_model=ConfigOut)
async def update_config(
    body: ConfigUpdateRequest,
    user: AdminUser,
    request: Request,
    container: ContainerDep,
    session: SessionDep,
) -> ConfigOut:
    runtime = container.runtime
    if body.seq_weight is not None:
        runtime.seq_weight = body.seq_weight
    if body.stat_weight is not None:
        runtime.stat_weight = body.stat_weight
    if body.threshold is not None:
        runtime.threshold = body.threshold

    await container.audit(session).record(
        actor_id=user.id,
        action="update_config",
        resource="runtime",
        ip=request.client.host if request.client else None,
        metadata={
            "seq_weight": runtime.seq_weight,
            "stat_weight": runtime.stat_weight,
            "threshold": runtime.threshold,
        },
    )
    return _current(container)
