"""FastAPI application factory and middleware wiring for Stellar P2P Ramp."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from stellar_p2p.api.auth import router as auth_router
from stellar_p2p.api.health import router as health_router
from stellar_p2p.api.trades import router as trades_router
from stellar_p2p.auth import NonceStore
from stellar_p2p.config import Settings, get_settings
from stellar_p2p.errors import register_error_handlers

logger = logging.getLogger("stellar_p2p.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle manager validating operational invariants."""
    # Enforce startup validation: missing required configuration aborts startup
    settings: Settings = getattr(app.state, "settings", None) or get_settings()
    logger.info("Initializing Stellar P2P Ramp API on network: %s", settings.stellar_network)

    if settings.stellar_network != "testnet":
        raise RuntimeError("Operational safety failure: non-testnet network configured.")

    yield
    logger.info("Shutting down Stellar P2P Ramp API.")


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Instantiate and configure the FastAPI application.

    Wires configuration, structured error formatting, CORS middleware,
    and typed route handlers.
    """
    app = FastAPI(
        title="Stellar P2P Ramp API",
        description="FastAPI scaffold for decentralized Stellar USDC/NGN escrow ramp.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Bind active configuration and isolated nonce store to application state
    app.state.settings = settings
    app.state.nonce_store = NonceStore()

    # Wire CORS middleware
    cors_origins = settings.cors_origins if settings else ["http://localhost:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Centralized structured error handling
    register_error_handlers(app)

    # Register routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(trades_router)

    return app


def get_app() -> FastAPI:
    """Factory entrypoint for ASGI runners (uvicorn --factory stellar_p2p.app:get_app)."""
    return create_app()
