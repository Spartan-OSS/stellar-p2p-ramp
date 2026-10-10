"""Pure transition model. Actors are identifiers, NOT authenticated identities.

The future Soroban contract must enforce these rules with require_auth; the API
must derive identities from verified sessions, never caller-provided strings.
"""
from dataclasses import dataclass, replace
from enum import Enum


class State(str, Enum):
    FUNDED = "funded"
    PAYMENT_CLAIMED = "payment_claimed"
    DISPUTED = "disputed"
    RELEASED = "released"
    REFUNDED = "refunded"


class Action(str, Enum):
    CLAIM_PAYMENT = "claim_payment"
    CONFIRM_RECEIPT = "confirm_receipt"
    EXPIRE = "expire"
    DISPUTE = "dispute"
    RESOLVE_BUYER = "resolve_buyer"
    RESOLVE_SELLER = "resolve_seller"


class InvalidTransition(ValueError):
    pass


@dataclass(frozen=True)
class Trade:
    trade_id: str
    seller: str
    buyer: str
    resolver: str
    usdc_units: int
    ngn_kobo: int
    payment_deadline: int
    state: State = State.FUNDED

    def __post_init__(self):
        if not self.trade_id or not all((self.seller, self.buyer, self.resolver)):
            raise ValueError("Identifiers are required")
        if len({self.seller, self.buyer, self.resolver}) != 3:
            raise ValueError("Buyer, seller and resolver must be distinct")
        for value in (self.usdc_units, self.ngn_kobo, self.payment_deadline):
            if type(value) is not int or value <= 0:
                raise ValueError("Amounts and deadline must be positive integers")


def transition(trade: Trade, action: Action, actor: str, now: int) -> Trade:
    if type(now) is not int or now < 0:
        raise ValueError("Time must be a nonnegative integer")
    if trade.state in {State.RELEASED, State.REFUNDED}:
        raise InvalidTransition("Trade is terminal")
    target = None
    if action == Action.CLAIM_PAYMENT:
        if actor == trade.buyer and trade.state == State.FUNDED and now < trade.payment_deadline:
            target = State.PAYMENT_CLAIMED
    elif action == Action.CONFIRM_RECEIPT:
        if actor == trade.seller and trade.state == State.PAYMENT_CLAIMED:
            target = State.RELEASED
    elif action == Action.EXPIRE:
        if trade.state == State.FUNDED and now >= trade.payment_deadline:
            target = State.REFUNDED
    elif action == Action.DISPUTE:
        # A buyer with a late or failed payment-claim transaction can still
        # dispute an unrefunded escrow. Ledger transaction ordering governs races.
        if actor in {trade.buyer, trade.seller} and trade.state in {State.FUNDED, State.PAYMENT_CLAIMED}:
            target = State.DISPUTED
    elif action in {Action.RESOLVE_BUYER, Action.RESOLVE_SELLER}:
        if actor == trade.resolver and trade.state == State.DISPUTED:
            target = State.RELEASED if action == Action.RESOLVE_BUYER else State.REFUNDED
    if target is None:
        raise InvalidTransition("Action is not allowed for this actor, state or time")
    return replace(trade, state=target)
