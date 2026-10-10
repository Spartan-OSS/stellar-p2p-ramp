# Security

This pre-alpha package includes a Soroban escrow and a disposable-account testnet script. It must not handle real funds. The Python domain reference models permissions using strings; it does not verify signatures. The Soroban contract enforces participant authorisation on-chain.

Before public launch, configure private GitHub vulnerability reporting or publish a monitored security contact. Report potential fund-loss or identity-data issues privately through that channel. Do not include real credentials or identity documents in public issues.

Required engineering checks: wallet-authenticated actors; replay-resistant signing; fixed asset issuer/contract; immutable trade terms; integer amounts; idempotent event processing; participant-only evidence access; refund/claim race handling; TTL/archival recovery; no arbitrary resolver payout; double-release protection.

Real-money deployment remains a separate milestone requiring contract review, operational dispute procedures and the relevant regulatory/payment-partner arrangements.
