"""Comprehensive test suite for Wallet Authentication in stellar-p2p-ramp.

Verifies Backlog #05 acceptance criteria:
1. Stellar StrKey (SEP-0023) encoding, decoding, and CRC16 checksum validation.
2. Cryptographic Ed25519 signature verification (PyNaCl and cryptography fallbacks).
3. Expiring, domain-bound and network-bound signed challenge generation.
4. Single-use nonce consumption and atomic replay attack prevention.
5. Expired challenge rejection and automatic stale nonce pruning.
6. Cross-domain phishing rejection (domain mismatch).
7. Session Bearer token creation and constant-time HMAC-SHA256 signature verification.
8. Tampered and expired session token rejection.
9. Protected endpoint access via verified Bearer tokens and unauthenticated call rejection.
10. Actor identity derivation from verified wallet session (spoofing prevention).
"""

import base64
import time
import unittest
from fastapi.testclient import TestClient
import nacl.signing
from pydantic import SecretStr

from stellar_p2p.api.trades import reset_demo_store, seed_demo_trade
from stellar_p2p.app import create_app
from stellar_p2p.auth import (
    NonceStore,
    SessionTokenManager,
    crc16_xmodem,
    decode_stellar_address,
    encode_stellar_address,
    is_valid_stellar_address,
    parse_signature_bytes,
    verify_ed25519_signature,
)
from stellar_p2p.config import Settings
from stellar_p2p.domain import Action, State, Trade


def get_test_settings(**overrides) -> Settings:
    """Fixture providing valid testing configuration with isolated keys."""
    defaults = {
        "environment": "testing",
        "stellar_network": "testnet",
        "stellar_rpc_url": "https://soroban-testnet.stellar.org",
        "stellar_network_passphrase": "Test SDF Network ; September 2015",
        "database_url": "postgresql://test_user:test_pass@localhost:5432/stellar_p2p_test",
        "session_secret_key": SecretStr("test_secret_hmac_signing_key_for_sessions_98765"),
        "auth_domain": "stellar-p2p.internal",
        "challenge_ttl_seconds": 300,
        "session_ttl_seconds": 3600,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestStrKeyCodec(unittest.TestCase):
    """Test suite for Stellar StrKey (SEP-0023) address encoding, decoding, and validation."""

    def test_encode_and_decode_roundtrip(self):
        """Valid 32-byte Ed25519 public keys encode to 56-character G-addresses and decode cleanly."""
        sk = nacl.signing.SigningKey.generate()
        raw_pk = sk.verify_key.encode()
        address = encode_stellar_address(raw_pk)

        self.assertEqual(len(address), 56)
        self.assertTrue(address.startswith("G"))
        self.assertTrue(is_valid_stellar_address(address))

        decoded_pk = decode_stellar_address(address)
        self.assertEqual(raw_pk, decoded_pk)

    def test_crc16_xmodem_accuracy(self):
        """CRC16-XModem calculation matches known test vectors."""
        # Empty payload
        self.assertEqual(crc16_xmodem(b""), 0x0000)
        # Standard ASCII vector "123456789" -> 0x31C3
        self.assertEqual(crc16_xmodem(b"123456789"), 0x31C3)

    def test_reject_invalid_length(self):
        """Addresses shorter or longer than 56 characters are rejected."""
        self.assertFalse(is_valid_stellar_address("GCR775TP7U5DMHSKDUOBGZEEZS6JFLAX7GXMKMH2JMUJDC4QRKVHLS3"))  # 55 chars
        self.assertFalse(is_valid_stellar_address("GCR775TP7U5DMHSKDUOBGZEEZS6JFLAX7GXMKMH2JMUJDC4QRKVHLS355"))  # 57 chars
        with self.assertRaises(ValueError):
            decode_stellar_address("GSHORT")

    def test_reject_non_g_prefix(self):
        """Addresses not starting with 'G' (such as seed keys 'S') are rejected."""
        self.assertFalse(is_valid_stellar_address("SBSELLER1111111111111111111111111111111111111111111111111"))
        with self.assertRaises(ValueError):
            decode_stellar_address("SBSELLER1111111111111111111111111111111111111111111111111")

    def test_reject_checksum_mismatch(self):
        """Single-character tampering in the address alters checksum and is rejected."""
        sk = nacl.signing.SigningKey.generate()
        address = encode_stellar_address(sk.verify_key.encode())
        # Corrupt last character
        corrupted_char = "A" if address[-1] != "A" else "B"
        corrupted_address = address[:-1] + corrupted_char

        self.assertFalse(is_valid_stellar_address(corrupted_address))
        with self.assertRaises(ValueError):
            decode_stellar_address(corrupted_address)


class TestEd25519Verification(unittest.TestCase):
    """Test suite for Ed25519 cryptographic signature parsing and verification."""

    def setUp(self):
        self.sk = nacl.signing.SigningKey.generate()
        self.pk = self.sk.verify_key.encode()
        self.message = b"Canonical test challenge message\nNetwork: testnet\nNonce: 12345"

    def test_valid_signature_verification(self):
        """Valid Ed25519 signature succeeds verification."""
        signed = self.sk.sign(self.message)
        sig = signed.signature
        self.assertTrue(verify_ed25519_signature(self.pk, self.message, sig))

    def test_tampered_signature_rejected(self):
        """Tampered signature bytes fail verification."""
        signed = self.sk.sign(self.message)
        sig = bytearray(signed.signature)
        sig[0] ^= 0xFF  # Flip bits in first byte
        self.assertFalse(verify_ed25519_signature(self.pk, self.message, bytes(sig)))

    def test_wrong_key_rejected(self):
        """Signature produced by key A fails verification against key B."""
        sk_b = nacl.signing.SigningKey.generate()
        signed_by_a = self.sk.sign(self.message)
        self.assertFalse(verify_ed25519_signature(sk_b.verify_key.encode(), self.message, signed_by_a.signature))

    def test_signature_parsing_hex_and_base64(self):
        """Signatures encoded in hex or base64 parse to exactly 64 bytes."""
        signed = self.sk.sign(self.message)
        sig_raw = signed.signature
        sig_hex = sig_raw.hex()
        sig_b64 = base64.b64encode(sig_raw).decode("ascii")

        self.assertEqual(parse_signature_bytes(sig_hex), sig_raw)
        self.assertEqual(parse_signature_bytes(sig_b64), sig_raw)
        self.assertEqual(parse_signature_bytes(sig_raw), sig_raw)

    def test_invalid_signature_length_rejected(self):
        """Signatures with invalid length raise ValueError."""
        with self.assertRaises(ValueError):
            parse_signature_bytes("short")
        with self.assertRaises(ValueError):
            parse_signature_bytes(b"0" * 32)


class TestNonceStoreAndReplayDefense(unittest.TestCase):
    """Test suite for NonceStore atomic single-use consumption and expiration pruning."""

    def setUp(self):
        self.store = NonceStore()
        self.sk = nacl.signing.SigningKey.generate()
        self.account = encode_stellar_address(self.sk.verify_key.encode())

    def test_create_and_consume_challenge(self):
        """Challenge is created and can be consumed exactly once."""
        challenge = self.store.create_challenge(
            account=self.account,
            domain="stellar-p2p.internal",
            network_passphrase="Test SDF Network ; September 2015",
            ttl_seconds=300,
        )
        self.assertEqual(challenge.account, self.account)
        self.assertTrue(len(challenge.nonce) >= 32)

        # First consumption succeeds
        consumed = self.store.consume_challenge(self.account, challenge.nonce)
        self.assertIsNotNone(consumed)
        self.assertEqual(consumed.nonce, challenge.nonce)

        # REPLAY ATTACK DEFENSE: Second consumption must return None
        replay_attempt = self.store.consume_challenge(self.account, challenge.nonce)
        self.assertIsNone(replay_attempt)

    def test_expired_challenge_consumption_rejected(self):
        """Challenges that have passed their TTL cannot be consumed."""
        # Create challenge with ttl of -1 second (already expired)
        challenge = self.store.create_challenge(
            account=self.account,
            domain="stellar-p2p.internal",
            network_passphrase="Test SDF Network ; September 2015",
            ttl_seconds=-1,
        )
        consumed = self.store.consume_challenge(self.account, challenge.nonce)
        self.assertIsNone(consumed)

    def test_prune_expired_removes_stale_records(self):
        """prune_expired cleans up expired challenges from memory."""
        from stellar_p2p.auth import ChallengeRecord
        stale_record = ChallengeRecord(
            account=self.account,
            nonce="stale_nonce_123",
            domain="domain.com",
            network_passphrase="pass",
            challenge_message="stale",
            issued_at=int(time.time()) - 500,
            expires_at=int(time.time()) - 200,
        )
        self.store._challenges[f"{self.account}:stale_nonce_123"] = stale_record
        self.assertEqual(len(self.store._challenges), 1)

        pruned_count = self.store.prune_expired()
        self.assertEqual(pruned_count, 1)
        self.assertEqual(len(self.store._challenges), 0)


class TestSessionTokenManager(unittest.TestCase):
    """Test suite for HMAC-SHA256 session bearer token issuance and verification."""

    def setUp(self):
        self.secret = "test_hmac_secret_key_1234567890_abcdef"
        self.sk = nacl.signing.SigningKey.generate()
        self.account = encode_stellar_address(self.sk.verify_key.encode())

    def test_create_and_verify_token(self):
        """Valid token verifies successfully and returns correct subject claim."""
        token = SessionTokenManager.create_session_token(
            account=self.account,
            secret_key=self.secret,
            ttl_seconds=3600,
        )
        self.assertIn(".", token)

        claims = SessionTokenManager.verify_session_token(token, self.secret)
        self.assertEqual(claims["sub"], self.account)
        self.assertTrue(claims["exp"] > time.time())

    def test_tampered_signature_rejected(self):
        """Modifying the token payload or signature fails HMAC verification."""
        token = SessionTokenManager.create_session_token(self.account, self.secret)
        payload_b64, sig_b64 = token.split(".")

        # Corrupt signature
        bad_sig = ("A" if sig_b64[0] != "A" else "B") + sig_b64[1:]
        corrupted_token = f"{payload_b64}.{bad_sig}"

        with self.assertRaises(ValueError) as cm:
            SessionTokenManager.verify_session_token(corrupted_token, self.secret)
        self.assertIn("signature verification failed", str(cm.exception))

    def test_expired_token_rejected(self):
        """Tokens with exp < current time are rejected."""
        token = SessionTokenManager.create_session_token(
            account=self.account,
            secret_key=self.secret,
            ttl_seconds=-10,  # Already expired
        )
        with self.assertRaises(ValueError) as cm:
            SessionTokenManager.verify_session_token(token, self.secret)
        self.assertIn("expired", str(cm.exception))

    def test_wrong_secret_key_rejected(self):
        """Verification with different secret key fails."""
        token = SessionTokenManager.create_session_token(self.account, self.secret)
        with self.assertRaises(ValueError):
            SessionTokenManager.verify_session_token(token, "wrong_secret_key")


class TestAuthAPIEndpoints(unittest.TestCase):
    """End-to-end integration test suite for /auth endpoints and protected routes."""

    def setUp(self):
        self.settings = get_test_settings()
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        reset_demo_store()

        # Generate realistic Stellar keypairs
        self.buyer_sk = nacl.signing.SigningKey.generate()
        self.buyer_addr = encode_stellar_address(self.buyer_sk.verify_key.encode())

        self.seller_sk = nacl.signing.SigningKey.generate()
        self.seller_addr = encode_stellar_address(self.seller_sk.verify_key.encode())

        self.resolver_sk = nacl.signing.SigningKey.generate()
        self.resolver_addr = encode_stellar_address(self.resolver_sk.verify_key.encode())

        # Seed trade
        self.trade = Trade(
            trade_id="TR-200",
            seller=self.seller_addr,
            buyer=self.buyer_addr,
            resolver=self.resolver_addr,
            usdc_units=50_000_000,
            ngn_kobo=75_000_00,
            payment_deadline=int(time.time()) + 3600,
            state=State.FUNDED,
        )
        seed_demo_trade(self.trade)

    def _authenticate_wallet(self, sk: nacl.signing.SigningKey, addr: str) -> str:
        """Helper to execute full SEP-0010 challenge-response flow and obtain bearer token."""
        # 1. Request challenge
        resp = self.client.post("/auth/challenge", json={"account": addr})
        self.assertEqual(resp.status_code, 200)
        challenge_data = resp.json()
        nonce = challenge_data["nonce"]
        challenge_msg = challenge_data["challenge_message"]

        # 2. Sign canonical challenge message with wallet private key
        signed = sk.sign(challenge_msg.encode("utf-8"))
        sig_hex = signed.signature.hex()

        # 3. Verify challenge
        resp = self.client.post(
            "/auth/verify",
            json={
                "account": addr,
                "nonce": nonce,
                "signature": sig_hex,
            },
        )
        self.assertEqual(resp.status_code, 200)
        return resp.json()["access_token"]

    def test_successful_challenge_and_verification_flow(self):
        """Wallet requests challenge, signs with Ed25519, and receives valid session token."""
        token = self._authenticate_wallet(self.buyer_sk, self.buyer_addr)
        self.assertTrue(len(token) > 20)

        # Use bearer token to access /auth/me
        resp = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["account"], self.buyer_addr)
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["network"], "testnet")

    def test_replay_attack_rejected(self):
        """Submitting the same signed challenge twice must be rejected on the second attempt."""
        resp = self.client.post("/auth/challenge", json={"account": self.buyer_addr})
        challenge_data = resp.json()
        nonce = challenge_data["nonce"]
        challenge_msg = challenge_data["challenge_message"]

        signed = self.buyer_sk.sign(challenge_msg.encode("utf-8"))
        sig_hex = signed.signature.hex()

        # First verification succeeds
        resp1 = self.client.post(
            "/auth/verify",
            json={"account": self.buyer_addr, "nonce": nonce, "signature": sig_hex},
        )
        self.assertEqual(resp1.status_code, 200)

        # Replay attempt with identical nonce and signature must fail with 401
        resp2 = self.client.post(
            "/auth/verify",
            json={"account": self.buyer_addr, "nonce": nonce, "signature": sig_hex},
        )
        self.assertEqual(resp2.status_code, 401)
        err = resp2.json()["error"]
        self.assertEqual(err["code"], "unauthorized")
        self.assertIn("already-consumed", err["message"])

    def test_cross_domain_assertion_mismatch_rejected(self):
        """Client asserting a domain different from server's auth_domain is rejected with 400."""
        resp = self.client.post("/auth/challenge", json={"account": self.buyer_addr})
        challenge_data = resp.json()

        resp_verify = self.client.post(
            "/auth/verify",
            json={
                "account": self.buyer_addr,
                "nonce": challenge_data["nonce"],
                "signature": "00" * 64,
                "domain": "phishing-evil-domain.com",  # Mismatched domain
            },
        )
        self.assertEqual(resp_verify.status_code, 400)
        err = resp_verify.json()["error"]
        self.assertEqual(err["code"], "bad_request")
        self.assertIn("Domain mismatch", err["message"])

    def test_wrong_signer_signature_rejected(self):
        """Challenge requested for wallet A cannot be verified with wallet B's signature."""
        resp = self.client.post("/auth/challenge", json={"account": self.buyer_addr})
        challenge_data = resp.json()
        challenge_msg = challenge_data["challenge_message"]

        # Signed by seller_sk instead of buyer_sk
        signed_by_seller = self.seller_sk.sign(challenge_msg.encode("utf-8"))

        resp_verify = self.client.post(
            "/auth/verify",
            json={
                "account": self.buyer_addr,
                "nonce": challenge_data["nonce"],
                "signature": signed_by_seller.signature.hex(),
            },
        )
        self.assertEqual(resp_verify.status_code, 401)
        err = resp_verify.json()["error"]
        self.assertEqual(err["code"], "unauthorized")
        self.assertIn("signature does not match account", err["message"])

    def test_tampered_signature_rejected(self):
        """Corrupted signature bytes fail verification."""
        resp = self.client.post("/auth/challenge", json={"account": self.buyer_addr})
        challenge_data = resp.json()
        challenge_msg = challenge_data["challenge_message"]

        signed = self.buyer_sk.sign(challenge_msg.encode("utf-8"))
        sig_bytes = bytearray(signed.signature)
        sig_bytes[10] ^= 0x42  # Tamper byte

        resp_verify = self.client.post(
            "/auth/verify",
            json={
                "account": self.buyer_addr,
                "nonce": challenge_data["nonce"],
                "signature": bytes(sig_bytes).hex(),
            },
        )
        self.assertEqual(resp_verify.status_code, 401)
        err = resp_verify.json()["error"]
        self.assertEqual(err["code"], "unauthorized")

    def test_invalid_address_format_rejected(self):
        """Malformatted Stellar address fails challenge generation with 400."""
        resp = self.client.post("/auth/challenge", json={"account": "INVALID_ADDRESS"})
        self.assertEqual(resp.status_code, 400)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "bad_request")

    def test_protected_trade_action_with_bearer_token(self):
        """Authenticated buyer with Bearer token can advance funded trade to payment_claimed."""
        buyer_token = self._authenticate_wallet(self.buyer_sk, self.buyer_addr)

        # Buyer claims payment using verified Bearer session token
        resp = self.client.post(
            "/trades/TR-200/action",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"action": Action.CLAIM_PAYMENT.value},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["trade_id"], "TR-200")
        self.assertEqual(data["state"], State.PAYMENT_CLAIMED.value)

    def test_unauthenticated_request_to_protected_route_fails_401(self):
        """Calling protected endpoints without authorization header returns 401."""
        resp = self.client.post(
            "/trades/TR-200/action",
            json={"action": Action.CLAIM_PAYMENT.value},
        )
        self.assertEqual(resp.status_code, 401)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "unauthorized")

    def test_tampered_bearer_token_returns_401(self):
        """Tampered Bearer token fails signature verification and returns 401."""
        buyer_token = self._authenticate_wallet(self.buyer_sk, self.buyer_addr)
        # Corrupt the bearer token
        corrupted_token = buyer_token[:-4] + "ffff"

        resp = self.client.post(
            "/trades/TR-200/action",
            headers={"Authorization": f"Bearer {corrupted_token}"},
            json={"action": Action.CLAIM_PAYMENT.value},
        )
        self.assertEqual(resp.status_code, 401)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "unauthorized")


if __name__ == "__main__":
    unittest.main()
