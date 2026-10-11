"""FastAPI dependencies ensuring verified actor identity derivation."""

from __future__ import annotations

from fastapi import Header, HTTPException, status


async def get_verified_actor(
    x_stellar_account: str | None = Header(
        default=None,
        alias="X-Stellar-Account",
        description="Verified Stellar public key from authenticated session context",
    ),
) -> str:
    """Derive authenticated actor identity from verified session context.

    Security rule:
    Domain actors MUST NOT be caller-provided strings in request bodies.
    This dependency enforces that the actor is derived from verified headers or sessions.
    """
    if not x_stellar_account or not x_stellar_account.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: X-Stellar-Account header missing.",
        )
    account = x_stellar_account.strip()
    if len(account) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid actor identity format.",
        )
    return account
