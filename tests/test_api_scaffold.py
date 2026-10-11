"""Unit test suite for FastAPI API scaffold in stellar_p2p.

Verifies:
1. Configuration validation with required fields and testnet-only constraint.
2. Protection of secrets (SecretStr never exposed in logs or string conversions).
3. Liveness (/health/live) and readiness (/health/ready) endpoint responses.
4. Structured error envelopes across 401, 404, 409 (domain conflict), and 422 validation.
5. Invariant that actors derive from verified session context, not request body strings.
6. Valid OpenAPI schema generation.
"""

import time
import unittest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from stellar_p2p.api.trades import reset_demo_store, seed_demo_trade
from stellar_p2p.app import create_app
from stellar_p2p.config import Settings
from stellar_p2p.domain import Action, State, Trade


def get_test_settings(**overrides) -> Settings:
    """Construct valid test settings fixture."""
    defaults = {
        "environment": "testing",
        "stellar_network": "testnet",
        "stellar_rpc_url": "https://soroban-testnet.stellar.org",
        "stellar_network_passphrase": "Test SDF Network ; September 2015",
        "database_url": "postgresql://test_user:test_pass@localhost:5432/stellar_p2p_test",
        "session_secret_key": SecretStr("super_secret_test_signing_key_12345"),
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestConfigValidation(unittest.TestCase):
    """Test suite for settings loading, validation, and secret masking."""

    def test_valid_configuration(self):
        """Ensure standard valid configuration instantiates cleanly."""
        settings = get_test_settings()
        self.assertEqual(settings.stellar_network, "testnet")
        self.assertEqual(settings.environment, "testing")
        self.assertTrue(settings.database_url)

    def test_missing_database_url_fails_startup(self):
        """Missing required database_url must raise ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            Settings(
                stellar_network="testnet",
                session_secret_key=SecretStr("secret_key"),
            )
        self.assertIn("database_url", str(cm.exception))

    def test_missing_session_secret_fails_startup(self):
        """Missing required session_secret_key must raise ValidationError."""
        with self.assertRaises(ValidationError) as cm:
            Settings(
                stellar_network="testnet",
                database_url="postgresql://localhost:5432/db",
            )
        self.assertIn("session_secret_key", str(cm.exception))

    def test_non_testnet_network_rejected(self):
        """Network configurations other than 'testnet' must be strictly rejected."""
        with self.assertRaises(ValidationError) as cm:
            get_test_settings(stellar_network="mainnet")
        self.assertIn("stellar_network", str(cm.exception))

    def test_secrets_masked_from_string_representation(self):
        """SecretStr must mask the session secret key and never reveal plaintext."""
        raw_secret = "confidential_production_signing_key_998877"
        settings = get_test_settings(session_secret_key=SecretStr(raw_secret))

        # Plain string representation and repr must be masked
        self.assertNotIn(raw_secret, str(settings))
        self.assertNotIn(raw_secret, repr(settings))
        self.assertNotIn(raw_secret, str(settings.safe_summary()))

        # Secret is accessible only via explicit get_secret_value()
        self.assertEqual(settings.session_secret_key.get_secret_value(), raw_secret)


class TestHealthEndpoints(unittest.TestCase):
    """Test suite for liveness and readiness monitoring."""

    def setUp(self):
        self.settings = get_test_settings()
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)

    def test_health_live_endpoint(self):
        """Liveness check returns 200 OK with expected payload."""
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "alive")
        self.assertEqual(data.get("service"), "stellar-p2p-ramp")

    def test_health_ready_endpoint(self):
        """Readiness check confirms testnet network and database readiness without leaking secrets."""
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ready")
        self.assertEqual(data.get("environment"), "testing")
        self.assertEqual(data.get("stellar_network"), "testnet")
        self.assertTrue(data.get("database_ready"))
        self.assertNotIn("postgresql://", response.text)
        self.assertNotIn("super_secret", response.text)


class TestStructuredErrorsAndActors(unittest.TestCase):
    """Test suite for structured error envelopes, actor authorization, and OpenAPI."""

    def setUp(self):
        self.settings = get_test_settings()
        self.app = create_app(self.settings)
        self.client = TestClient(self.app)
        reset_demo_store()

        self.seller = "GBSELLER1111111111111111111111111111111111111111111111111"
        self.buyer = "GBBUYER22222222222222222222222222222222222222222222222222"
        self.resolver = "GBRESOLVER33333333333333333333333333333333333333333333333"

        self.sample_trade = Trade(
            trade_id="TR-100",
            seller=self.seller,
            buyer=self.buyer,
            resolver=self.resolver,
            usdc_units=100_000_000,
            ngn_kobo=150_000_00,
            payment_deadline=int(time.time()) + 3600,
            state=State.FUNDED,
        )
        seed_demo_trade(self.sample_trade)

    def test_not_found_returns_structured_error(self):
        """404 errors must return uniform error JSON."""
        response = self.client.get("/trades/non_existent_trade_id")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "not_found")
        self.assertIn("not found", data["error"]["message"].lower())

    def test_validation_error_returns_structured_error(self):
        """422 errors must return uniform validation error JSON without internal tracebacks."""
        # Send invalid action payload
        response = self.client.post(
            "/trades/TR-100/action",
            headers={"X-Stellar-Account": self.buyer},
            json={"action": "invalid_unknown_action"},
        )
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "validation_error")
        self.assertIsInstance(data["error"]["details"], list)

    def test_unauthenticated_actor_returns_401(self):
        """Attempting to perform a trade action without verified actor returns 401."""
        response = self.client.post(
            "/trades/TR-100/action",
            json={"action": Action.CLAIM_PAYMENT.value},
        )
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "unauthorized")

    def test_actor_cannot_be_spoofed_in_request_body(self):
        """Caller cannot supply an unverified actor string in the request body."""
        # Attempt to pass an attacker actor in the JSON body while header is seller
        response = self.client.post(
            "/trades/TR-100/action",
            headers={"X-Stellar-Account": self.seller},
            json={
                "action": Action.CLAIM_PAYMENT.value,
                "actor": self.buyer,  # Body spoofing attempt
            },
        )
        # The transition must fail because the actual actor is derived from the header (seller),
        # and only the buyer is permitted to claim payment on a funded trade!
        self.assertEqual(response.status_code, 409)
        data = response.json()
        self.assertEqual(data["error"]["code"], "invalid_transition")

    def test_valid_authorized_transition_succeeds(self):
        """Buyer claiming payment with verified authentication advances trade state."""
        response = self.client.post(
            "/trades/TR-100/action",
            headers={"X-Stellar-Account": self.buyer},
            json={"action": Action.CLAIM_PAYMENT.value},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["trade_id"], "TR-100")
        self.assertEqual(data["state"], State.PAYMENT_CLAIMED.value)

    def test_openapi_schema_generated(self):
        """OpenAPI JSON spec is available and includes health and trade routes."""
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("openapi")[:2], "3.")
        self.assertEqual(data["info"]["title"], "Stellar P2P Ramp API")
        self.assertIn("/health/live", data["paths"])
        self.assertIn("/health/ready", data["paths"])
        self.assertIn("/trades/{trade_id}", data["paths"])
        self.assertIn("/auth/challenge", data["paths"])
        self.assertIn("/auth/verify", data["paths"])
        self.assertIn("/auth/me", data["paths"])


if __name__ == "__main__":
    unittest.main()
