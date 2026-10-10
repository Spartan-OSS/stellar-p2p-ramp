# Decision: original per-trade Soroban escrow

Status: selected for testnet prototype, 10 October 2026. Not an audit or production approval.

Trustless Work snapshot: `f0b706eaf6e98aa83bf4f95df42857b5d4c8e847`, branch `single-release-develop`.

| Requirement | Inspected upstream | Decision |
|---|---|---|
| Seller funds / buyer receives | Configurable roles | Can map |
| Wallet authorisation | `require_auth` in core funding/release/dispute operations | Present |
| Disputed release blocking | Release validation checks disputed flag | Present |
| Contract-enforced payment deadline | No deadline in `storage/types.rs`; no corresponding escrow entrypoint | Gap |
| Payment-claimed state blocks expiry | Generic milestone status; no equivalent expiry transition | Gap |
| Resolver restricted to recorded buyer/seller | Resolution accepts `Map<Address,i128>`; validator checks totals, not recipient membership | Gap |
| Licence to copy contracts | No standalone licence found in inspected branch | Unconfirmed |

A backend wrapper cannot remove a contract's direct-call permissions. These structural gaps rule out treating the inspected API as equivalent to our specification. Upstream executable integration tests were not run: the interface mismatch is sufficient to reject this snapshot for this design. Service fees/terms remain unverified and are not adopted. Future versions can be reassessed.

## Prototype design

One deployed escrow per trade. Constructor binds token, participants, amount, NGN quote and reference; there are no setters, upgrades, platform fees or arbitrary-recipient methods. The seller signs funding; buyer signs payment claim; seller signs receipt confirmation; either participant signs disputes; fixed resolver signs a binary buyer/seller outcome. Ledger timestamps govern expiry. Full principal is returned on refund. Token contract must be independently allowlisted by the deployment/application layer; the generic contract does not certify a token as Circle USDC.

Per-trade isolation simplifies accounting and provides a unique contract address. Trade reference uniqueness across contracts remains an application/database constraint, not a global on-chain guarantee. No bank receipt is verified by this contract.

## Remaining risks

Buyer payment/claim/expiry race; resolver inactivity; issuer freezes/clawbacks; token authenticity; asset trustlines; storage archival/restore; operational evidence access. Any accidental extra deposits remain outside the recorded principal and have no withdrawal method. No mainnet use before review. See ESCROW_SPEC for the bank-payment trust model.
