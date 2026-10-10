"""Signed CLI testnet walkthrough, using disposable accounts and DEMOUSD.

No mainnet support. No bank transfer. Keys exist only in memory, never output.
"""
import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path

import requests
from stellar_sdk import Asset, Keypair, Network, SorobanServer, TransactionBuilder, scval, xdr

RPC = "https://soroban-testnet.stellar.org"
NETWORK = Network.TESTNET_NETWORK_PASSPHRASE


def returned(result):
    meta = xdr.TransactionMeta.from_xdr(result.result_meta_xdr)
    details = meta.v4 if meta.v == 4 else meta.v3
    return details.soroban_meta.return_value


def run(wasm_path, output):
    rpc = SorobanServer(RPC)
    history = []
    keys = {role: Keypair.random() for role in ["issuer", "seller", "buyer", "resolver"]}
    for role, key in keys.items():
        response = requests.get("https://friendbot.stellar.org", params={"addr": key.public_key}, timeout=60)
        response.raise_for_status()
        print(f"Funded disposable {role} test account", flush=True)

    def builder(role):
        return TransactionBuilder(rpc.load_account(keys[role].public_key), NETWORK, base_fee=100).set_timeout(180)

    def send(role, b, label, soroban=True):
        tx = b.build()
        if soroban:
            tx = rpc.prepare_transaction(tx)
        tx.sign(keys[role])
        submitted = rpc.send_transaction(tx)
        if submitted.status.value not in {"PENDING", "DUPLICATE"}:
            raise RuntimeError(f"Submission failed for {label}: {submitted.status}")
        stop = time.monotonic() + 120
        while time.monotonic() < stop:
            result = rpc.get_transaction(submitted.hash)
            if result.status.value == "SUCCESS":
                history.append({"step": label, "signer": role, "hash": submitted.hash, "ledger": result.ledger,
                                "url": f"https://stellar.expert/explorer/testnet/tx/{submitted.hash}"})
                print(f"Confirmed {label}: {submitted.hash}", flush=True)
                return result
            if result.status.value == "FAILED":
                raise RuntimeError(f"Transaction failed for {label}: {result.result_xdr}")
            time.sleep(2)
        raise TimeoutError(f"Confirmation timed out for {label}; inspect {submitted.hash}")

    asset = Asset("DEMOUSD", keys["issuer"].public_key)
    for role in ["seller", "buyer", "resolver"]:
        send(role, builder(role).append_change_trust_op(asset), f"{role} trustline", False)
    send("issuer", builder("issuer").append_payment_op(keys["seller"].public_key, asset, "200"), "issue 200 DEMOUSD", False)
    send("issuer", builder("issuer").append_create_stellar_asset_contract_from_asset_op(asset), "deploy demo asset")
    token_id = asset.contract_id(NETWORK)
    wasm = Path(wasm_path).read_bytes()
    wasm_hash = hashlib.sha256(wasm).hexdigest()
    send("seller", builder("seller").append_upload_contract_wasm_op(wasm), "upload escrow wasm")

    def deploy(label):
        # Use ledger time, not local workstation time, for contract deadline.
        health = requests.post(RPC, json={"jsonrpc":"2.0", "id":1, "method":"getHealth"}, timeout=30).json()
        deadline = int(health["result"]["latestLedgerCloseTime"]) + 3600
        t = scval.to_struct({
            "seller": scval.to_address(keys["seller"].public_key),
            "buyer": scval.to_address(keys["buyer"].public_key),
            "resolver": scval.to_address(keys["resolver"].public_key),
            "token": scval.to_address(token_id), "amount": scval.to_int128(100 * 10**7),
            "ngn_kobo": scval.to_int128(150000 * 100), "deadline": scval.to_uint64(deadline),
            "reference": scval.to_bytes(secrets.token_bytes(32)),
        })
        result = send("seller", builder("seller").append_create_contract_op(wasm_hash, keys["seller"].public_key, [t], salt=secrets.token_bytes(32)), label)
        return scval.from_address(returned(result)).address

    def invoke(role, contract, function, parameters=None):
        return send(role, builder(role).append_invoke_contract_function_op(contract, function, parameters or []), function)

    def read(role, contract, function, parameters=None):
        tx = builder(role).append_invoke_contract_function_op(contract, function, parameters or []).build()
        simulation = rpc.simulate_transaction(tx)
        if simulation.error:
            raise RuntimeError(simulation.error)
        return xdr.SCVal.from_xdr(simulation.results[0].xdr)

    released = deploy("deploy release escrow")
    invoke("seller", released, "fund")
    invoke("buyer", released, "claim_payment")
    # This assertion does not claim to verify an actual naira transfer.
    invoke("seller", released, "confirm_receipt")
    assert scval.from_enum(read("buyer", released, "get_state"))[0] == "Released"

    refunded = deploy("deploy dispute escrow")
    invoke("seller", refunded, "fund")
    invoke("buyer", refunded, "claim_payment")
    invoke("buyer", refunded, "open_dispute", [scval.to_address(keys["buyer"].public_key)])
    invoke("resolver", refunded, "resolve", [scval.to_bool(False)])
    assert scval.from_enum(read("seller", refunded, "get_state"))[0] == "Refunded"
    balance = lambda address: scval.from_int128(read("seller", token_id, "balance", [scval.to_address(address)]))
    balances = {role: balance(keys[role].public_key) for role in ["seller","buyer","resolver"]}
    assert balances == {"seller":100*10**7,"buyer":100*10**7,"resolver":0}
    assert balance(released) == balance(refunded) == 0
    evidence = {"network":"testnet", "asset":"DEMOUSD — synthetic, not Circle USDC", "wasm_sha256":wasm_hash,
                "accounts":{r:k.public_key for r,k in keys.items()},
                "token_contract":token_id, "escrows":{"released":released,"refunded":refunded},
                "balances_base_units":balances, "transactions":history,
                "limitations":"CLI-held disposable keys; no browser wallet, real bank payment or real USDC"}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(evidence, indent=2)+"\n")
    print(f"Verified release and disputed refund; public evidence written to {output}")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--wasm", default="contracts/escrow/target/wasm32v1-none/release/p2p_escrow.wasm")
    parser.add_argument("--output", default="docs/testnet-evidence.json")
    args=parser.parse_args()
    run(args.wasm,args.output)
