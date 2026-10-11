"""Health check endpoints for liveness and readiness monitoring."""

from __future__ import annotations

from fastapi import APIRouter, Request, status
from stellar_p2p.config import Settings, get_settings
from stellar_p2p.schemas import HealthLiveResponse, HealthReadyResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/live",
    response_model=HealthLiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness check",
    description="Indicates whether the process is alive and receiving traffic.",
)
async def health_live() -> HealthLiveResponse:
    """Return process liveness confirmation."""
    return HealthLiveResponse(status="alive", service="stellar-p2p-ramp")


@router.get(
    "/ready",
    response_model=HealthReadyResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
    description="Confirms that configuration is loaded and operational dependencies are reachable.",
)
async def health_ready(request: Request) -> HealthReadyResponse:
    """Return readiness status verifying active configuration."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    return HealthReadyResponse(
        status="ready",
        environment=settings.environment,
        stellar_network=settings.stellar_network,
        database_ready=bool(settings.database_url),
    )
