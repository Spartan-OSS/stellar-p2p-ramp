# Escrow specification v0.1

Design target for implementation; the supplied Python model is only an executable reference. No deployed contract yet.

## Roles and immutable terms

USDC seller funds; USDC buyer receives tokens; an independently designated resolver adjudicates disputes. All three addresses are distinct. Bind trade ID, network, token contract/issuer, buyer, seller, resolver, amount, fee schedule and payment deadline. Keep bank details, identity documents and raw receipts off-chain. A terms/evidence commitment must not expose low-entropy personal information; use salted commitments where appropriate.

## State transitions

| State | Action | Authorisation | Next state |
|---|---|---|---|
| Awaiting funding (off-chain) | Fund exact agreed amount | Seller; parties accept terms | Funded |
| Funded | Claim payment before deadline | Buyer signature | Payment claimed |
| Funded | Expire at/after deadline | Anyone; fixed refund recipient | Refunded |
| Funded or payment claimed | Open dispute | Buyer or seller | Disputed |
| Payment claimed | Confirm naira receipt | Seller signature | Released |
| Disputed | Decide buyer wins | Fixed resolver signature | Released |
| Disputed | Decide seller wins | Fixed resolver signature | Refunded |
| Released or refunded | Any settlement action | None allowed | Reject |

Funded means on-chain funding confirmed. Off-chain reservation cancellation before funding cannot move escrow funds. Cooperative cancellation after funding and partial settlements are deferred until their exact authorisation/fee semantics are specified.

## Functions to implement

`create_and_fund(terms)`; `claim_payment(trade_id, evidence_commitment)`; `confirm_receipt(trade_id)`; `expire(trade_id)`; `open_dispute(trade_id)`; `resolve(trade_id, buyer_wins, decision_commitment)`; `get_trade(trade_id)`; `bump_ttl(trade_id)`.

Use the ledger timestamp for contractual deadlines, not an assumed fixed number of ledgers per minute. Deadline must be future and bounded by policy. Define USDC asset identity per network; a test token is never represented as redeemable mainnet USDC. Buyer classic account trustline readiness and contract/account recipient support must be checked before funding.

## Required invariants

- Only one terminal outcome; no duplicate payouts or trade-ID overwrite.
- Released tokens go only to the recorded buyer; refunds only to recorded seller.
- Resolver cannot change recipients, amounts or asset, and cannot settle an undisputed trade.
- No timeout refund after an on-chain payment claim or dispute.
- Receipt upload and a bank webhook alone cannot release funds.
- Total payouts cannot exceed funded value; fee and principal accounting are separate.
- Pausing new trades must preserve safe exits for existing funds.
- TTL maintenance and restoration procedures must cover prolonged disputes.

## Payment/deadline race

The buyer must allow enough time for the payment-claim transaction to confirm. Disable the UI's payment instruction near expiry using a documented safety margin. A server-side claim is not equivalent to an on-chain claim. If a bank transfer succeeds but the on-chain claim is delayed or fails, the buyer can dispute while escrow remains unrefunded; a confirmed refund cannot be undone. Ledger ordering decides simultaneous expiry/dispute transactions. This residual risk needs UI warnings, a sufficient claim window and operational escalation; neither this model nor an HTLC makes bank settlement atomic.

False payment claims can lock funds, so claims are assertions rather than receipt verification. Merchant/user limits, monitoring and a defined reviewer response process are required. Resolver inactivity can leave funds locked: establish reviewer continuity before live use; do not add a silent timeout payout that bypasses disputes.

## Integration gate

A Trustless Work adapter must prove these invariants in contract-level integration tests, including roles, deadlines, dispute blocking, payouts, fees and TTL. A backend-only deadline rule is insufficient if direct contract calls bypass it. If the upstream contract cannot express our requirements, implement an original minimal Soroban contract. Do not silently label an incompatible adapter as equivalent.
