# Signed testnet walkthrough

This walkthrough uses disposable testnet accounts with CLI-held keys and a synthetic `DEMOUSD` asset. It proves signed on-chain escrow transitions, not browser wallet UX, Circle USDC redemption or a real bank transfer. No mainnet option exists in the script. Private keys are generated in memory and never printed or written; after exit these disposable accounts are inaccessible. Testnet balances have no monetary value.

## Setup

Install stable Rust with the `wasm32v1-none` target and Python 3.11+:

```bash
rustup target add wasm32v1-none
cargo test --locked --manifest-path contracts/escrow/Cargo.toml
cargo build --locked --manifest-path contracts/escrow/Cargo.toml --target wasm32v1-none --release
python3 -m venv .venv
. .venv/bin/activate
pip install -r scripts/requirements-testnet.txt
python scripts/testnet_demo.py
```

The committed Cargo.lock avoids an incompatible ed25519-dalek 3.x resolution allowed by the SDK host's broad dependency constraint. Use `--locked`; dependency upgrades require testing.

## Expected execution

Friendbot funds issuer, seller, buyer and resolver. Seller/buyer/resolver establish demo asset trustlines; issuer supplies 200 DEMOUSD to seller. Script deploys the Stellar Asset Contract and uploads the escrow Wasm.

First escrow: seller funds 100; buyer claims simulated naira payment; seller confirms receipt; buyer receives 100. Second escrow: seller funds 100; buyer claims payment and disputes; resolver awards seller refund. Script verifies terminal states, final buyer/seller balances of 100 each, resolver balance zero and both escrow balances zero.

Public transaction hashes, contract addresses and balances are written to `docs/testnet-evidence.json`. The script does not store keys. The naira value is illustrative only. A failed/timed-out run raises an exception and does not claim success; if confirmation times out, inspect its hash before assuming failure. Re-running creates new accounts and contracts.

## Remaining work

Freighter browser signing, wallet session authentication, configured native USDC issuer/contract validation, API integration, evidence storage and bank-transfer operations. This testnet demonstration is a milestone towards these features.
