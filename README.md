# stellar-p2p-ramp

Stellar P2P Ramp — contributor foundation

Open-source infrastructure for exchanging Stellar USDC for local currency, starting with NGN bank transfers. Working title; no affiliation with Stellar Development Foundation, Circle, Drips or the reference projects.

## Current status

Pre-alpha design and executable Python domain reference. No live escrow, wallet integration, bank integration, KYC service or deployed marketplace. The reference model does not move money and does not authenticate wallet signatures. Do not use it to handle funds.

## Run the foundation

Python 3.10+:

```bash
# Run the test suite (domain + FastAPI scaffold tests)
python3 -m unittest discover -s tests -v
# Or with pytest:
pytest

# Run the domain simulation demo
python3 -m stellar_p2p.demo

# Run the FastAPI API server
export STELLAR_P2P_DATABASE_URL="postgresql://user:pass@localhost:5432/stellar_p2p"
export STELLAR_P2P_SESSION_SECRET_KEY="replace_with_your_cryptographic_secret"
uvicorn stellar_p2p.app:get_app --factory --reload
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs` and schema at `/openapi.json`.

### Wallet Authentication (SEP-0010 Challenge-Response)

1. **Request a signed challenge**:
   `POST /auth/challenge` with `{"account": "G..."}`.
   Returns domain- and network-bound challenge message with a single-use nonce.
2. **Sign locally**:
   Sign the canonical challenge message with wallet Ed25519 private key (e.g. Freighter wallet).
3. **Verify and receive session token**:
   `POST /auth/verify` with `{"account": "G...", "nonce": "...", "signature": "<hex_or_base64>"}`.
   Nonces are consumed immediately upon verification to prevent replay attacks. Returns an HMAC-SHA256 signed Bearer session token.
4. **Access protected endpoints**:
   Pass header `Authorization: Bearer <access_token>`. All domain actor identities are derived strictly from the verified session.


## Product scope

- USDC/NGN merchant offers with explicit quotes and limits.
- Seller-funded Stellar escrow; buyer pays naira directly to seller.
- Signed payment claim, seller confirmation and controlled dispute resolution.
- Encrypted off-chain payment evidence and traceable trade history.
- Configurable fiat adapters so other communities can add local payment methods.

Read [architecture](docs/ARCHITECTURE.md), [escrow specification](docs/ESCROW_SPEC.md), [research](docs/RESEARCH.md), [roadmap](docs/ROADMAP.md), [application draft](docs/APPLICATION.md) and [contributor backlog](docs/BACKLOG.md).

## Implementation direction

Next.js/TypeScript UI, FastAPI API, PostgreSQL, a Stellar event worker, and a Rust/Soroban escrow implementation behind an adapter. Evaluate Trustless Work integration against our state-machine requirements before choosing it over an original contract. NGN remains off-chain. No platform token, bridges or automated receipt-based release in the initial scope.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Work is tracked in the backlog; issue templates are supplied for publishing to GitHub. All new code in this package is original. Reference repositories are not bundled.

## Licence

MIT for original files in this package. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Upstream licences must be checked separately before importing upstream code.
