"""Typed Pydantic request and response schemas for the Stellar P2P Ramp API.

Enforces strict domain types:
- Integer base units for USDC (stroops/units) and integer NGN kobo.
- Actor identities are derived from verified session context, never accepted
  as caller-provided request body strings (prevents identity spoofing).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from stellar_p2p.domain import Action, State


class OfferSide(str, Enum):
    """Direction of the offer relative to USDC."""

    SELL = "sell"
    BUY = "buy"


# ---------------------------------------------------------------------------
# Health Schemas
# ---------------------------------------------------------------------------


class HealthLiveResponse(BaseModel):
    """Liveness probe response model."""

    status: str = Field(default="alive", description="Process health status")
    service: str = Field(default="stellar-p2p-ramp", description="Service identifier")


class HealthReadyResponse(BaseModel):
    """Readiness probe response model."""

    status: str = Field(default="ready", description="Application readiness status")
    environment: str = Field(..., description="Target environment")
    stellar_network: str = Field(..., description="Target Stellar network (testnet)")
    database_ready: bool = Field(default=True, description="Database connection health")


# ---------------------------------------------------------------------------
# Trade & Domain Schemas
# ---------------------------------------------------------------------------


class TradeResponse(BaseModel):
    """Representation of an active or settled trade projection."""

    trade_id: str = Field(..., description="Unique trade identifier")
    seller: str = Field(..., description="Stellar address of the USDC seller")
    buyer: str = Field(..., description="Stellar address of the USDC buyer")
    resolver: str = Field(..., description="Designated escrow dispute resolver address")
    usdc_units: int = Field(..., gt=0, description="USDC amount in base units (integer)")
    ngn_kobo: int = Field(..., gt=0, description="Fiat amount in NGN kobo (integer)")
    payment_deadline: int = Field(..., gt=0, description="Unix timestamp payment expiration deadline")
    state: State = Field(..., description="Current escrow state machine state")


class TradeActionRequest(BaseModel):
    """Action payload for advancing a trade's state.

    SECURITY INVARIANT:
    Notice there is NO 'actor' field in this request body.
    Domain actors must not become unverified request-body identities.
    The actor identity must be derived by the API from authenticated session context.
    """

    action: Action = Field(..., description="State transition action to apply")


# ---------------------------------------------------------------------------
# Offer & Quote Schemas
# ---------------------------------------------------------------------------


class OfferCreateRequest(BaseModel):
    """Merchant liquidity offer creation parameters."""

    side: OfferSide = Field(..., description="Direction: sell USDC or buy USDC")
    rate_ngn_per_usdc: str = Field(..., description="Exact fiat rate formatted as decimal string")
    min_usdc_units: int = Field(..., gt=0, description="Minimum trade size in USDC base units")
    max_usdc_units: int = Field(..., gt=0, description="Maximum trade size in USDC base units")
    available_usdc_units: int = Field(..., gt=0, description="Total inventory available")


class QuoteRequest(BaseModel):
    """Parameters for requesting an immutable trade quote snapshot."""

    offer_id: str = Field(..., description="ID of the target offer")
    usdc_units: int = Field(..., gt=0, description="Requested USDC base units")


class QuoteResponse(BaseModel):
    """Immutable quote snapshot model."""

    quote_id: str = Field(..., description="Unique quote identifier")
    offer_id: str = Field(..., description="Source offer identifier")
    usdc_units: int = Field(..., description="Exact USDC base units to trade")
    ngn_kobo: int = Field(..., description="Calculated NGN kobo amount")
    expiry_timestamp: int = Field(..., description="Quote expiration deadline (Unix epoch)")
