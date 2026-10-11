"""Trades router exercising pure domain transitions with verified actor identities."""

from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException, status

from stellar_p2p.api.deps import get_verified_actor
from stellar_p2p.domain import Trade, transition
from stellar_p2p.schemas import TradeActionRequest, TradeResponse

router = APIRouter(prefix="/trades", tags=["trades"])

# In-memory store for API demonstration and testing purposes
# Production implementation will project from PostgreSQL and Soroban events
_DEMO_TRADES: dict[str, Trade] = {}


def reset_demo_store() -> None:
    """Helper for test suites to clear demo trade state."""
    _DEMO_TRADES.clear()


def seed_demo_trade(trade: Trade) -> None:
    """Helper for test suites to populate sample trades."""
    _DEMO_TRADES[trade.trade_id] = trade


@router.get(
    "/{trade_id}",
    response_model=TradeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get trade status",
    description="Retrieve projected escrow trade state by ID.",
)
async def get_trade(trade_id: str) -> TradeResponse:
    """Return trade state or raise 404 if not found."""
    trade = _DEMO_TRADES.get(trade_id)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade '{trade_id}' not found.",
        )
    return TradeResponse(
        trade_id=trade.trade_id,
        seller=trade.seller,
        buyer=trade.buyer,
        resolver=trade.resolver,
        usdc_units=trade.usdc_units,
        ngn_kobo=trade.ngn_kobo,
        payment_deadline=trade.payment_deadline,
        state=trade.state,
    )


@router.post(
    "/{trade_id}/action",
    response_model=TradeResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute trade state transition",
    description="Apply a verified state transition using the authenticated actor identity.",
)
async def execute_trade_action(
    trade_id: str,
    request: TradeActionRequest,
    actor: str = Depends(get_verified_actor),
) -> TradeResponse:
    """Apply transition to trade using actor derived from verified session."""
    trade = _DEMO_TRADES.get(trade_id)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade '{trade_id}' not found.",
        )

    now = int(time.time())
    updated_trade = transition(trade, request.action, actor, now)
    _DEMO_TRADES[trade_id] = updated_trade

    return TradeResponse(
        trade_id=updated_trade.trade_id,
        seller=updated_trade.seller,
        buyer=updated_trade.buyer,
        resolver=updated_trade.resolver,
        usdc_units=updated_trade.usdc_units,
        ngn_kobo=updated_trade.ngn_kobo,
        payment_deadline=updated_trade.payment_deadline,
        state=updated_trade.state,
    )
