# Architecture and scope

## Problem and users

Stellar USDC holders need a transparent way to find local-currency counterparties and complete trades. The first reference corridor is USDC/NGN bank transfer, aimed at freelancers receiving stablecoins and merchants supplying local liquidity. These are hypotheses to validate through interviews, not measured adoption claims.

## Components

| Component | Responsibilities | Trust boundary |
|---|---|---|
| Web UI, Next.js/TypeScript | Offers, quotes, wallet signing, trade timeline, disputes | Never stores signing secrets or privileged service credentials |
| API, FastAPI | Sessions, offers, quote reservation, payment instructions, evidence access | Cannot release funds using a database flag |
| PostgreSQL | Offers, immutable quote snapshots, chain projections, audit log | Database status is a projection, not settlement truth |
| Stellar event worker | Verify transactions, project contract events, reconcile gaps | Match network, contract, asset, participants and amount |
| Escrow adapter | Prepare unsigned transactions; query confirmed state | Supports original Soroban or evaluated Trustless Work integration |
| Soroban escrow | Enforce custody, participant actions and resolution | Designated resolver can decide disputed funds only |
| Fiat adapter | Payment instructions and optional verified payment signals | A bank signal is not an atomic on-chain fiat swap |
| Evidence store | Encrypted receipts and dispute records | Signed short-lived access, participant/reviewer authorisation |

## Data model

users; wallets (unique network/address); merchants; payment_accounts (encrypted, ownership status); offers (side, currency, available quantity, rate, limits, version); quotes (expiry, exact amounts, rounding policy, payment-account snapshot); trades (quote, participants, resolver, contract, funding transaction, projected status); chain_events (unique network/tx/event-index); disputes; evidence; audit_events; outbox.

Seller always means the USDC seller. Buyer always means the USDC buyer, regardless of which party published the offer. Reserve offer inventory inside a database transaction with row locking or a conditional update. Redis may cache offers but must not be the authoritative inventory ledger.

Use integer token base units read from the configured asset decimals and integer NGN kobo; represent rates as decimal strings/rational values. Define rounding explicitly. Never use binary floats for financial amounts. Quote amount, fee, deadline and participants become immutable when funded. Fees start at zero in the reference implementation; a future fee schedule must specify refund behaviour and cap fees.

## Authentication and settlement

Wallet connection alone is not authentication. Use a signed, expiring, domain-bound challenge with a one-use nonce or an appropriate Stellar authentication standard. Derive API identities from verified sessions. Wallets sign escrow actions locally. The backend returns unsigned transactions only after validation; the UI verifies destinations, network and amounts before requesting signatures.

The API acknowledges submitted transactions as pending. Funding, payment claim, release and refund become confirmed only after successful ledger inclusion and verified contract state/events. Workers deduplicate events and can reconstruct state after restart. API command idempotency keys are scoped to user, operation and request body; conflicting reuse is rejected.

## Initial boundaries

Testnet, one pair, bank-transfer instructions, synthetic identity/payment evidence and a small merchant workflow. No real bank integration, claims of regulatory approval or guaranteed liquidity. No NGN token, cross-chain bridge, DeFi, platform token, mobile native client or AI dispute decisions in MVP.

The reusable output is a fiat-adapter interface, escrow adapter, event projector and reference UX; Nigeria is the initial implementation case. This distinguishes the project from a renamed generic escrow marketplace.
