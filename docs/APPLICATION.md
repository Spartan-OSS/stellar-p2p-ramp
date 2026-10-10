# Maintainer programme application draft

Working title: Stellar P2P Ramp

## Short description

An open-source Stellar USDC-to-local-currency marketplace foundation, starting with NGN bank transfers. It combines seller-funded escrow, wallet-signed trade actions, a clear dispute model and reusable fiat-payment adapters.

## Problem

Holding a stablecoin does not provide local spending access by itself. Users need liquidity discovery, clear local-payment instructions and protection when a counterparty disputes receipt. We are developing a reference marketplace that makes escrow authority and settlement status explicit while keeping sensitive bank and identity data off-chain.

## Stellar ecosystem contribution

Stellar is the settlement layer: the proposed escrow uses Soroban and Stellar USDC. The open-source deliverables include an escrow specification and implementation, a reusable integration adapter, reliable event projection, wallet-connected trade UX and a documented fiat-adapter interface. NGN is the first case study, with currency-specific payment instructions separated from the settlement engine.

## Existing foundation — accurate as of 10 October 2026

We have an original Python domain model and nine passing tests covering participant permissions, deadline boundaries, dispute protection and terminal states; repository contribution templates; an architecture/specification; a pinned comparison of MicoPay, Pacto, Trustless Work and MarketX; and scoped contributor tasks.

Public repository: https://github.com/Spartan-OSS/stellar-p2p-ramp

We do not yet have a deployed Soroban contract, wallet-connected demo, payment integration, customers or regulatory approval. Replace this paragraph as implementation advances. Do not describe a reference model as a functioning exchange.

## Requested contributor work

Rust/Soroban engineers for escrow and adversarial tests; Python engineers for API, reservations and event workers; TypeScript engineers for signing and trade UI; reviewers for threat modelling, accessibility and documentation. The initial cycle should focus on independently reviewable issues, not an entire exchange assigned as one task.

## Maintenance plan

Proposed maintainer: Jeremiah Ojonuba. Maintainer will own specification decisions, issue assignment and PR review. Before submission, confirm review availability, publish a security contact and test the contributor setup on a clean machine. State only commitments the maintainer can sustain.

## Differentiation

Our focus is the bank-payment failure model and reusable local-currency integration: payment-claim/deadline races, restricted arbitration recipients, immutable quote terms and verified chain state. MicoPay provides a cash/QR reference; Pacto provides the strongest regional bank-payment reference. This project will credit those references and contribute reusable infrastructure rather than simply rebrand their interfaces.

## Programme route

Drips Stellar Wave is a relevant candidate. Official maintainer docs require a GitHub organisation, installation of its GitHub App, public repository synchronisation, an explicit application to the relevant programme and organiser approval. Contributors apply to approved issues; maintainers select and assign them. Participation does not guarantee acceptance, staffing, security review or a dedicated project budget.

Source: https://docs.drips.network/wave/maintainers/participating-in-a-wave/

## Submission readiness

The official onboarding process above is verified. The following are our recommended quality milestones, not asserted programme eligibility requirements:

1. Publish a clearly licensed repository with honest status and reproducible CI.
2. Deliver one complete testnet flow with actual wallet signatures and chain-confirmed escrow.
3. Demonstrate both release and disputed refund; document residual bank-payment risk.
4. Prepare 6–10 scoped issues with dependencies, tests and acceptance criteria.
5. Confirm reviewer capacity, private security contact and upstream licence decisions.
6. Apply and await approval before adding issues to the programme.

Do not submit unsupported adoption, audit, compliance, revenue or uptime claims.
