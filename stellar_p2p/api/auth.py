"""Authentication endpoints for Web3 Stellar wallet challenge-response."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status

from stellar_p2p.api.deps import get_verified_actor
from stellar_p2p.auth import (
    SessionTokenManager,
    decode_stellar_address,
    default_nonce_store,
    is_valid_stellar_address,
    parse_signature_bytes,
    verify_ed25519_signature,
)
from stellar_p2p.config import Settings, get_settings
from stellar_p2p.schemas import (
    ActorInfoResponse,
    AuthTokenResponse,
    ChallengeRequest,
    ChallengeResponse,
    VerifyChallengeRequest,
)

logger = logging.getLogger("stellar_p2p.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_active_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", None) or get_settings()


def _get_nonce_store(request: Request):
    return getattr(request.app.state, "nonce_store", None) or default_nonce_store


@router.post(
    "/challenge",
    response_model=ChallengeResponse,
    summary="Generate domain- and network-bound challenge",
    description=(
        "Issues an expiring, single-use cryptographic challenge for a target Stellar wallet. "
        "The generated challenge message binds the server domain, target network passphrase, "
        "and a unique cryptographic nonce to prevent replay and cross-domain phishing attacks."
    ),
)
async def request_challenge(
    payload: ChallengeRequest,
    request: Request,
) -> ChallengeResponse:
    account = payload.account.strip()
    if not is_valid_stellar_address(account):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stellar public address format: must be valid 56-character SEP-0023 G-address.",
        )

    settings = _get_active_settings(request)
    nonce_store = _get_nonce_store(request)

    challenge = nonce_store.create_challenge(
        account=account,
        domain=settings.auth_domain,
        network_passphrase=settings.stellar_network_passphrase,
        ttl_seconds=settings.challenge_ttl_seconds,
    )

    return ChallengeResponse(
        account=challenge.account,
        nonce=challenge.nonce,
        domain=challenge.domain,
        network_passphrase=challenge.network_passphrase,
        challenge_message=challenge.challenge_message,
        issued_at=challenge.issued_at,
        expires_at=challenge.expires_at,
    )


@router.post(
    "/verify",
    response_model=AuthTokenResponse,
    summary="Verify challenge signature and issue session bearer token",
    description=(
        "Verifies an Ed25519 signature over a previously issued challenge message. "
        "The nonce is consumed immediately upon lookup to prevent replay attacks. "
        "Upon successful verification, issues an HMAC-SHA256 signed session bearer token."
    ),
)
async def verify_challenge(
    payload: VerifyChallengeRequest,
    request: Request,
) -> AuthTokenResponse:
    account = payload.account.strip()
    if not is_valid_stellar_address(account):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stellar public address format: must be valid 56-character SEP-0023 G-address.",
        )

    settings = _get_active_settings(request)

    # Optional cross-domain check if caller explicitly provided an asserted domain
    if payload.domain and payload.domain.strip() != settings.auth_domain:
        logger.warning(
            "Rejected cross-domain authentication attempt: client domain '%s' != server domain '%s'",
            payload.domain,
            settings.auth_domain,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domain mismatch: challenge domain must be '{settings.auth_domain}'.",
        )

    # Decode public key bytes
    try:
        pubkey_bytes = decode_stellar_address(account)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to decode Stellar public key: {exc}",
        ) from exc

    # Parse signature bytes
    try:
        sig_bytes = parse_signature_bytes(payload.signature)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signature format or length: {exc}",
        ) from exc

    # Single-use consumption of challenge nonce
    nonce_store = _get_nonce_store(request)
    challenge = nonce_store.consume_challenge(account=account, nonce=payload.nonce.strip())

    if challenge is None:
        logger.warning(
            "Rejected challenge verification for %s: nonce not found, already consumed, or expired.",
            account,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or already-consumed challenge nonce.",
        )

    # Cryptographic Ed25519 verification over the exact canonical challenge text
    message_bytes = challenge.challenge_message.encode("utf-8")
    is_valid = verify_ed25519_signature(pubkey_bytes, message_bytes, sig_bytes)

    if not is_valid:
        logger.warning("Cryptographic signature verification failed for account %s", account)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cryptographic signature verification failed: signature does not match account.",
        )

    # Issue session bearer token
    token = SessionTokenManager.create_session_token(
        account=account,
        secret_key=settings.session_secret_key.get_secret_value(),
        ttl_seconds=settings.session_ttl_seconds,
    )

    logger.info("Successfully authenticated Stellar wallet %s", account)
    return AuthTokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=settings.session_ttl_seconds,
        account=account,
    )


@router.get(
    "/me",
    response_model=ActorInfoResponse,
    summary="Get authenticated wallet profile",
    description="Returns the verified Stellar account identity derived from the active session.",
)
async def get_current_actor_profile(
    request: Request,
    actor: str = Depends(get_verified_actor),
) -> ActorInfoResponse:
    settings = _get_active_settings(request)
    return ActorInfoResponse(
        account=actor,
        authenticated=True,
        network=settings.stellar_network,
    )
