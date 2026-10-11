"""Configuration validation with strict testnet defaults and secret protection."""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("stellar_p2p.config")


class Settings(BaseSettings):
    """Application configuration with environment-driven loading.

    Enforces testnet-only network configuration and validates that essential
    infrastructure keys (database URL, session secret) are present before startup.
    """

    model_config = SettingsConfigDict(
        env_prefix="STELLAR_P2P_",
        env_file=".env",
        extra="ignore",
    )

    # Core environment
    environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)",
    )

    # Enforce testnet-only default per ARCHITECTURE.md and Issue #2 acceptance criteria
    stellar_network: Literal["testnet"] = Field(
        default="testnet",
        description="Stellar network target. MVP strictly limits target to testnet.",
    )

    stellar_rpc_url: str = Field(
        default="https://soroban-testnet.stellar.org",
        description="Stellar Soroban RPC endpoint",
    )

    stellar_network_passphrase: str = Field(
        default="Test SDF Network ; September 2015",
        description="Stellar network passphrase",
    )

    # Required operational secrets and infrastructure targets
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string. Required for state projection.",
    )

    session_secret_key: SecretStr = Field(
        ...,
        description="Cryptographic secret key for signing session tokens. Masked from logs.",
    )

    api_host: str = Field(
        default="127.0.0.1",
        description="Host interface for the API server",
    )

    api_port: int = Field(
        default=8000,
        description="Port for the API server",
    )

    auth_domain: str = Field(
        default="stellar-p2p.internal",
        description="Domain for challenge verification (prevents cross-domain replay attacks)",
    )

    challenge_ttl_seconds: int = Field(
        default=300,
        description="TTL for authentication challenges in seconds (default 5 minutes)",
    )

    session_ttl_seconds: int = Field(
        default=86400,
        description="TTL for session bearer tokens in seconds (default 24 hours)",
    )

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins for the frontend client",
    )

    @field_validator("stellar_network")
    @classmethod
    def validate_testnet_only(cls, value: str) -> str:
        if value != "testnet":
            raise ValueError(
                f"Invalid stellar_network '{value}'. The MVP strictly permits 'testnet' only."
            )
        return value

    def safe_summary(self) -> dict[str, Any]:
        """Return a dictionary of safe settings without leaking any secrets."""
        return {
            "environment": self.environment,
            "stellar_network": self.stellar_network,
            "stellar_rpc_url": self.stellar_rpc_url,
            "api_host": self.api_host,
            "api_port": self.api_port,
            "auth_domain": self.auth_domain,
            "challenge_ttl_seconds": self.challenge_ttl_seconds,
            "session_ttl_seconds": self.session_ttl_seconds,
            "database_url_configured": bool(self.database_url),
            "session_secret_configured": bool(self.session_secret_key),
        }


def get_settings() -> Settings:
    """Load settings from environment variables."""
    return Settings()
