# stellar-p2p-ramp

Stellar P2P Ramp — contributor foundation

Open-source infrastructure for exchanging Stellar USDC for local currency, starting with NGN bank transfers. Working title; no affiliation with Stellar Development Foundation, Circle, Drips or the reference projects.

## Current status

Pre-alpha: an original Soroban escrow contract, executable Python domain reference and signed CLI testnet walkthrough. Browser wallet integration, bank integration, KYC and the marketplace are still pending. The demo uses disposable accounts and a synthetic token, not redeemable USDC. No mainnet use.

## Run the foundation

Python 3.11+, no third-party dependencies:

```bash
python3 -m unittest discover -s tests -v
python3 -m stellar_p2p.demo
```

## Product scope

- USDC/NGN merchant offers with explicit quotes and limits.
- Seller-funded Stellar escrow; buyer pays naira directly to seller.
- Signed payment claim, seller confirmation and controlled dispute resolution.
- Encrypted off-chain payment evidence and traceable trade history.
- Configurable fiat adapters so other communities can add local payment methods.

Read [architecture](docs/ARCHITECTURE.md), [escrow specification](docs/ESCROW_SPEC.md), [research](docs/RESEARCH.md), [roadmap](docs/ROADMAP.md), [application draft](docs/APPLICATION.md) and [contributor backlog](docs/BACKLOG.md).

The [escrow decision](docs/ESCROW_DECISION.md) explains why this prototype uses an original per-trade contract. Follow the [signed testnet walkthrough](docs/TESTNET_WALKTHROUGH.md) to compile, test and exercise it.

## Implementation direction

Next.js/TypeScript UI, FastAPI API, PostgreSQL, a Stellar event worker, and the original Rust/Soroban escrow implementation. The inspected Trustless Work contract did not meet our fixed-recipient/deadline invariants. NGN remains off-chain. No platform token, bridges or automated receipt-based release in the initial scope.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Work is tracked in the backlog; issue templates are supplied for publishing to GitHub. All new code in this package is original. Reference repositories are not bundled.

## Licence

MIT for original files in this package. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Upstream licences must be checked separately before importing upstream code.

## Browser reviewer demo

[Open the public prototype](https://spartan-stellar-p2p.greengecko4.chatgpt.site). Try the wallet-free guided trade, or use Freighter with three testnet accounts for real escrow transactions. [Setup and deployment guide](web/README.md). Uses synthetic DEMOUSD; no real USDC or naira. Live JavaScript client release and refund evidence is in [browser-testnet-evidence.json](docs/browser-testnet-evidence.json).
