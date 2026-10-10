# Contributor backlog

Proposed tasks; not published issues or programme-approved work. Complexity is provisional; split tasks that cannot fit one sprint. Programme points must follow organiser rules at submission time.

## 01 — Escrow adapter feasibility (high, Rust/integration)

Compare Trustless Work's pinned interface with ESCROW_SPEC. Deliver a capability matrix, licence/service-terms findings and executable tests for role mapping, disputed release rejection, claim/timeout behaviour and fixed payouts. Recommend integrate or original contract. Depends: specification review. Out of scope: marketplace UI or mainnet deployment.

## 02 — Minimal original Soroban escrow (high, Rust; split into implementation and adversarial tests)

If 01 rejects equivalence, implement seller funding, claim, release, expiry, dispute and binary resolver outcome. Acceptance: `require_auth` for participant actions, distinct roles, unique IDs, integer safe arithmetic, pinned token, no arbitrary payout, timestamps and storage TTL. Test conservation and all invalid actors/states. Depends: 01 decision. Do not port upstream code with unresolved licensing.

## 03 — Wallet-signing vertical slice (high, TypeScript)

Connect Freighter on testnet, validate network, show transaction terms, sign locally and display pending/confirmed/failure states. Acceptance: actual confirmed seller funding and release with explorer evidence; wrong network and rejected signatures handled. Depends: escrow interface. Out of scope: storing private keys or mainnet.

## 04 — FastAPI API scaffold (medium, Python)

Add configuration validation, health endpoints, typed schemas, structured errors and OpenAPI. Acceptance: testnet-only default, missing required config fails startup, no secrets in responses/logs and reproducible installation. Domain actors must not become unverified request-body identities. Depends: none.

## 05 — Wallet authentication (high, Python/TypeScript)

Implement expiring, domain/network-bound signed challenges and single-use nonce consumption. Acceptance: signature verification, replay/cross-domain/expired challenges rejected, session identity derives from verified wallet, protected endpoints reject unauthenticated calls. Depends: 04; integration with 03.

## 06 — PostgreSQL offers and atomic reservations (high, Python)

Add migrations and reserve/release inventory transactionally. Acceptance: concurrent buyers cannot overbook; expired unfunded reservations restore inventory exactly once; all values use integers/decimals; pagination stable. Depends: 04/05. Use real database concurrency tests, not mocks alone.

## 07 — Immutable quotes (medium, Python)

Persist buyer/seller, amount, NGN total, rate, rounding, fee, payment-account snapshot and expiry. Acceptance: edits to offers cannot change accepted quote; stale acceptance rejected; decimal rounding covered by examples; idempotency conflicts rejected. Depends: 06.

## 08 — Stellar event projector (high, Python)

Consume successful contract events using checkpointing and unique event IDs. Acceptance: replay and worker restart produce identical state; unsuccessful or wrong-contract/asset transactions cannot mark funded; reconciliation fills missed ranges. Depends: escrow interface and 04. Submission of a transaction is not funding confirmation.

## 09 — NGN bank-transfer adapter (medium, Python)

Define adapter interface and a synthetic NGN implementation exposing verified-account-style instructions and exact quote amounts. Acceptance: explicit mock designation, payment reference, participant-only access and no screenshot-triggered settlement. Depends: 07/05. Live banking is deferred.

## 10 — Trade timeline and deadline UX (medium, TypeScript)

Render funded, payment-claimed, disputed and terminal states from confirmed chain projections. Acceptance: payment instructions withheld before funding; deadline safety margin; pending claim never presented as confirmed; refund/claim race explained; accessible keyboard operation. Depends: 03/08/09.

## 11 — Evidence and dispute workspace (high; split storage and reviewer UI)

Encrypted off-chain evidence with scoped uploads/downloads; designated reviewer sees decisions and exact permitted recipients. Acceptance: strangers cannot access evidence; safe upload limits and retention policy; decision requires resolver wallet signature; audit record includes result without raw PII. Depends: 05/08/10.

## 12 — Testnet walkthrough and clean-machine contributor setup (medium, docs/QA)

Document exact dependency versions, synthetic accounts, asset configuration, funding, release and disputed refund. Acceptance: fresh checkout runs tests and walkthrough; references use real testnet transactions with no secrets; known limitations explicit. Depends: vertical slice. A video alone does not replace reproducible commands.

## Recommended first contribution cycle

Start with 01, 04, 05 and design review; then activate dependent tasks only when interfaces are stable. The maintainer should own security-critical merges and avoid assigning every dependent issue simultaneously.
