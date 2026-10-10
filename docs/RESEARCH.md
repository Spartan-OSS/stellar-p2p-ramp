# Repository inspection — 10 October 2026

Scope: shallow clones of current default branches; selected contract, integration and configuration files read. Upstream builds/tests were not run. This is a targeted architecture/licensing inspection, not a comprehensive audit. Commit pins identify what was actually inspected; later upstream changes may differ.

| Repository | Inspected commit |
|---|---|
| https://github.com/Micopay/micopay-protocol | 1cf65e22b81d86f43bbe40cc3c1ec3bce04ec8c6 |
| https://github.com/Trustless-Work/trustlesswork-smart-contract-stellar | f0b706eaf6e98aa83bf4f95df42857b5d4c8e847 |
| https://github.com/MarketXpress/MarketX-frontend | 719a46bad4c0522957ef4ad61557fdbcaf9af92e |
| https://github.com/MarketXpress/MarketX-backend | 20019960f179d499bb646bf85f630531980bff3b |
| https://github.com/MarketXpress/MarketX-contract | 8498252a24292436863d6e8787bfc0f6e2b680a1 |
| https://github.com/PACTO-LAT/pacto-connect | 347652d331e223bca36c48643b227d27fa64bf1d |
| https://github.com/PACTO-LAT/pacto-p2p | 6d8aad016684060c7e2b9e30eaeb7a96ea5bcab7 |

## MicoPay

Read README, LICENSE and `micopay/contracts/escrow/src/lib.rs`. MIT licence present. The escrow locks seller tokens, releases to the buyer with buyer authorisation plus a secret preimage, and refunds the seller after a ledger-based timeout. It extends storage TTL and rejects existing trade IDs. No payment-claimed/disputed state or resolver appears in this inspected escrow module. Its refund and release eligibility can overlap after timeout, so transaction order matters. That is not suitable unchanged for a bank-transfer flow where payment can precede a dispute. We will use the cash-access product concept as a reference, not copy its escrow for NGN bank transfers. README distinguishes testnet/demo flows from unfinished matching/banking work.

## Trustless Work

Default branch inspected: `single-release-develop`. Read contract entrypoints, dispute core, role types and README. It provides role-based escrow, milestone approval, release and dispute functions; dispute resolution requires the designated resolver's authorisation. Inspecting those functions is not sufficient to guarantee our deadline/claim semantics. No standalone licence file found in this snapshot: permission to copy is unconfirmed. Proposed use is an adapter feasibility evaluation, subject to service terms and invariant tests, not an automatic fork. Relevant files: `contracts/escrow/src/contract.rs`, `core/dispute.rs`, `core/validators/dispute.rs`, `storage/types.rs`.

## MarketX

Read frontend README/package metadata, backend package metadata and contract escrow entrypoints/documentation. The project uses a commerce escrow model: buyer-funded purchases and delivery-oriented release. That reverses the funder/recipient roles compared with selling USDC for fiat. Next.js/Freighter frontend and NestJS/Postgres/Redis backend provide architecture references, not proven production-readiness. Backend package declares `UNLICENSED`; no standalone licence file found in the frontend or contract snapshots. Do not copy source until permissions are resolved. Borrow design lessons such as reservation concurrency, event indexing and TTL maintenance through original implementation.

## Pacto P2P and Pacto Connect

Pacto is the closest product reference: regional fiat rails, merchant listings and Trustless Work trade funding/release hooks. Read P2P README/package metadata, `apps/web/hooks/use-trades.ts` integration references and `apps/web/lib/services/stellar.ts`. The latter contains mock wallet/balance/payment helpers; this does not imply all signing hooks are mocked. README advertises MIT but no standalone licence file was found. Resolve the licence grant before copying. It configures a browser-visible Trustless Work key; our implementation must classify provider keys and keep privileged credentials server-side.

Pacto Connect includes an MIT licence and separates a gateway from embeddable core/React/web-component/mobile SDKs. Useful future integration pattern; not necessary for the first trade demo. No upstream code is copied into this starter.

## Foundation decisions

1. Original project, explicit NGN case study and reusable fiat adapters.
2. Bank-transfer workflow informed by Pacto; cash/HTLC model is not equivalent.
3. Escrow backend selected only after invariant tests; evaluate Trustless Work first.
4. Python backend aligns with maintainer skills; Rust contract and TypeScript wallet UI are contributor tracks.
5. Publish honest prototype status, source attribution and licence decisions.
6. Contributor tasks address working infrastructure, not cosmetic issue farming.

## Additional primary sources

- Pacto role mapping: https://www.trustlesswork.com/escrow-times/use-case-decentralized-p2p
- Drips maintainer onboarding: https://docs.drips.network/wave/maintainers/participating-in-a-wave/
- Stellar Wave: https://www.drips.network/wave/stellar

Contributor participation and repository approval are separate. We have not submitted this project or obtained approval.
