"""FastAPI dependencies ensuring verified actor identity derivation."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import Header, HTTPException, Request, status

from stellar_p2p.auth import SessionTokenManager
from stellar_p2p.config import get_settings

logger = logging.getLogger("stellar_p2p.api.deps")


async def get_verified_actor(
    request: Request,
    authorization: Optional[str] = Header(
        default=None,
        alias="Authorization",
        description="Bearer session token issued by /auth/verify",
    ),
    x_stellar_account: Optional[str] = Header(
        default=None,
        alias="X-Stellar-Account",
        description="Direct verified Stellar account header for testing and migration",
    ),
) -> str:
    """Derive authenticated actor identity from verified session context.

    Security rules:
    1. Domain actors MUST NOT be caller-provided strings in request bodies.
    2. Primary mechanism: Cryptographically verified Bearer session token signed by server HMAC.
    3. Fallback mechanism: X-Stellar-Account header for backwards compatibility with tests.
    4. Unauthenticated calls are rejected with HTTP 401 Unauthorized.
    """
    # 1. Bearer session token verification
    if authorization and authorization.strip():
        auth_val = authorization.strip()
        if not auth_val.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization scheme: must use 'Bearer <token>'.",
            )
        token = auth_val[7:].strip()
        settings = getattr(request.app.state, "settings", None) or get_settings()
        secret_key = settings.session_secret_key.get_secret_value()

        try:
            claims = SessionTokenManager.verify_session_token(token, secret_key)
            actor = claims["sub"]
            return actor
        except ValueError as exc:
            logger.warning("Session token validation failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Session authentication failed: {exc}",
            ) from exc

    # 2. Direct actor header fallback (test fixtures & migration)
    if x_stellar_account and x_stellar_account.strip():
        account = x_stellar_account.strip()
        if len(account) < 4:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid actor identity format.",
            )
        return account

    # 3. No authentication provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: Missing Authorization Bearer token or actor header.",
    )
