# Reviewer browser demo

Public preview: https://spartan-stellar-p2p.greengecko4.chatgpt.site

`npm ci && npm run dev` starts local development. `npm test && npm run build` validates and builds `dist/`. Deploy `dist/` to any static host; no server, secrets or environment variables are required. Node 24 is used in CI.

## Review without a wallet

Select Guided walkthrough. As seller lock the tokens; switch to buyer and mark payment sent; switch to seller and confirm receipt. Restart and open a dispute, then select resolver and refund the seller or release to buyer. This mode is entirely simulated and labeled accordingly.

## Review with Freighter

1. Install Freighter, select Stellar Testnet, and create three distinct accounts.
2. Connect each account and use Friendbot to fund it with test XLM.
3. Save the seller, buyer and resolver public addresses.
4. Connect seller and create an escrow (may require two signatures: asset deployment and escrow deployment).
5. Switch to buyer, reconnect, and add the DEMOUSD trustline.
6. Switch to seller, reconnect, and lock 10 DEMOUSD.
7. Switch to buyer, reconnect, and mark the simulated naira payment sent.
8. Switch to seller and confirm receipt, or open a dispute and switch to resolver to resolve.

The seller is the issuer of a fresh synthetic DEMOUSD asset. No Circle USDC or real naira moves. The quote is fixed at 10 DEMOUSD / ₦15,000. The buyer trustline is needed for token delivery. An unclaimed funded escrow can be refunded after the 60-minute deadline; claimed payments require seller confirmation or resolver intervention.

Only public addresses, contract ID and public trade terms are saved in browser localStorage. Keys stay in Freighter. Refresh queries confirmed contract state. Signing checks the active account and testnet passphrase. Loading an escrow verifies the deployed WASM hash, asset identity and supported quote before enabling actions. Transactions display pending status, confirmed status and explorer links. If confirmation times out, refresh before retrying.

Testnet resets or archival can invalidate stored contracts or the uploaded WASM. Redeploy using the CLI walkthrough and update the reviewed hash when required. RPC/Friendbot availability and browser extension permissions are external dependencies.

`node test/live-smoke.js` is an opt-in live integration test using disposable in-memory keys. It issues a synthetic token and tests release and disputed refund through the exact same client used by the UI. It is excluded from routine CI. Never use mainnet keys.

This is a contribution prototype: no bank verification, identity checks, marketplace backend or production audit. A payment claim is only an assertion; the resolver is trusted. The wallet-free walkthrough does not exercise Freighter. Extension popup approval and visual browser QA must be checked manually before calling the browser integration fully validated.
