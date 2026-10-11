"""Cryptographic wallet authentication module for Stellar P2P Ramp.

Implements SEP-0010 / Web3 challenge-response authentication with:
- Stellar StrKey decoding and CRC16-XModem checksum validation (SEP-0023).
- Ed25519 cryptographic signature verification (via PyNaCl and cryptography).
- Domain-bound and network-bound signed challenge generation.
- Expiring, single-use nonce consumption (replay attack prevention).
- Tamper-proof session bearer token issuance and verification (HMAC-SHA256).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import nacl.exceptions
import nacl.signing
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger("stellar_p2p.auth")


# ---------------------------------------------------------------------------
# Stellar StrKey (SEP-0023) Codec & CRC16-XModem
# ---------------------------------------------------------------------------


def crc16_xmodem(data: bytes) -> int:
    """Calculate CRC16-XModem checksum (polynomial 0x1021, init 0x0000)."""
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def decode_stellar_address(address: str) -> bytes:
    """Decode a 56-character Base32 Stellar Account ID (G...) into raw 32-byte Ed25519 public key.

    Validates:
    - Exactly 56 characters starting with 'G'.
    - Valid Base32 payload (35 bytes: 1 byte version 0x30 + 32 bytes pubkey + 2 bytes CRC16).
    - Version byte must be 0x30 (ed25519 public key).
    - CRC16-XModem checksum match (little-endian).
    """
    if not isinstance(address, str) or len(address) != 56 or not address.startswith("G"):
        raise ValueError(
            "Invalid Stellar public address format: must be 56 characters starting with 'G'."
        )

    try:
        raw = base64.b32decode(address.upper())
    except Exception as exc:
        raise ValueError(f"Invalid Base32 encoding in Stellar address: {exc}") from exc

    if len(raw) != 35:
        raise ValueError(
            f"Invalid decoded length for Stellar address: expected 35 bytes, got {len(raw)}."
        )

    version = raw[0]
    if version != 0x30:
        raise ValueError(
            f"Invalid version byte in Stellar address: expected 0x30 (AccountID), got 0x{version:02x}."
        )

    pubkey = raw[1:33]
    checksum = raw[33:35]
    expected_crc = crc16_xmodem(raw[:33])
    actual_crc = checksum[0] | (checksum[1] << 8)

    if expected_crc != actual_crc:
        raise ValueError("CRC16 checksum mismatch in Stellar address.")

    return pubkey


def encode_stellar_address(raw_pubkey: bytes) -> str:
    """Encode a 32-byte raw Ed25519 public key into a 56-character Base32 Stellar Account ID."""
    if len(raw_pubkey) != 32:
        raise ValueError(f"Ed25519 public key must be exactly 32 bytes, got {len(raw_pubkey)}.")
    payload = bytes([0x30]) + raw_pubkey
    crc = crc16_xmodem(payload)
    full = payload + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    return base64.b32encode(full).decode("ascii")


def is_valid_stellar_address(address: str) -> bool:
    """Check whether a string is a valid Stellar public address."""
    try:
        decode_stellar_address(address)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cryptographic Signature Verification
# ---------------------------------------------------------------------------


def parse_signature_bytes(signature: str | bytes) -> bytes:
    """Parse signature from raw bytes, hex string, or base64 string.

    Returns exactly 64 bytes.
    """
    if isinstance(signature, bytes):
        sig_bytes = signature
    elif isinstance(signature, str):
        sig_str = signature.strip()
        # Attempt hex decoding first (128 hex chars)
        if len(sig_str) == 128:
            try:
                sig_bytes = bytes.fromhex(sig_str)
            except ValueError:
                sig_bytes = base64.b64decode(sig_str)
        else:
            try:
                sig_bytes = base64.b64decode(sig_str)
            except Exception:
                sig_bytes = bytes.fromhex(sig_str)
    else:
        raise ValueError("Signature must be str (hex or base64) or bytes.")

    if len(sig_bytes) != 64:
        raise ValueError(
            f"Invalid Ed25519 signature length: expected 64 bytes, got {len(sig_bytes)}."
        )
    return sig_bytes


def verify_ed25519_signature(pubkey_bytes: bytes, message: bytes, signature_bytes: bytes) -> bool:
    """Verify an Ed25519 signature against the raw public key and message.

    Uses PyNaCl with fallback to the cryptography package.
    """
    if len(pubkey_bytes) != 32:
        return False
    if len(signature_bytes) != 64:
        return False

    # Primary verification using PyNaCl
    try:
        verify_key = nacl.signing.VerifyKey(pubkey_bytes)
        verify_key.verify(message, signature_bytes)
        return True
    except (nacl.exceptions.BadSignatureError, nacl.exceptions.CryptoError):
        return False
    except Exception:
        pass

    # Fallback verification using cryptography primitives
    try:
        crypto_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
        crypto_key.verify(signature_bytes, message)
        return True
    except (InvalidSignature, Exception):
        return False


# ---------------------------------------------------------------------------
# Challenge Generation and Nonce Management
# ---------------------------------------------------------------------------


def build_challenge_message(
    domain: str,
    network_passphrase: str,
    account: str,
    nonce: str,
    expires_at: int,
) -> str:
    """Format canonical challenge message for wallet signing."""
    return (
        f"{domain} auth challenge\n"
        f"Network: {network_passphrase}\n"
        f"Account: {account}\n"
        f"Nonce: {nonce}\n"
        f"Expires: {expires_at}"
    )


@dataclass(frozen=True)
class ChallengeRecord:
    """Immutable record of an active challenge issued to a wallet."""

    account: str
    nonce: str
    domain: str
    network_passphrase: str
    challenge_message: str
    issued_at: int
    expires_at: int


class NonceStore:
    """Thread-safe in-memory store for authentication nonces.

    Enforces:
    - Single-use consumption (preventing replay attacks).
    - Expiration verification (now <= expires_at).
    - Periodic pruning of stale nonces.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._challenges: dict[str, ChallengeRecord] = {}

    def create_challenge(
        self,
        account: str,
        domain: str,
        network_passphrase: str,
        ttl_seconds: int = 300,
    ) -> ChallengeRecord:
        """Create and store a domain/network-bound challenge with single-use nonce."""
        with self._lock:
            self._prune_expired_locked()
            nonce = secrets.token_hex(32)
            now = int(time.time())
            expires_at = now + ttl_seconds
            challenge_msg = build_challenge_message(
                domain=domain,
                network_passphrase=network_passphrase,
                account=account,
                nonce=nonce,
                expires_at=expires_at,
            )
            record = ChallengeRecord(
                account=account,
                nonce=nonce,
                domain=domain,
                network_passphrase=network_passphrase,
                challenge_message=challenge_msg,
                issued_at=now,
                expires_at=expires_at,
            )
            key = f"{account}:{nonce}"
            self._challenges[key] = record
            return record

    def consume_challenge(self, account: str, nonce: str) -> ChallengeRecord | None:
        """Atomically retrieve and remove a challenge for verification.

        CRITICAL SECURITY INVARIANT:
        The record is popped immediately. This guarantees that whether the
        subsequent signature verification succeeds or fails, the nonce can NEVER
        be submitted or replayed a second time.
        """
        with self._lock:
            key = f"{account}:{nonce}"
            record = self._challenges.pop(key, None)
            if record is None:
                return None
            now = int(time.time())
            if now > record.expires_at:
                logger.warning(
                    "Challenge nonce for account %s has expired (now=%s, exp=%s)",
                    account,
                    now,
                    record.expires_at,
                )
                return None
            return record

    def _prune_expired_locked(self) -> None:
        now = int(time.time())
        expired_keys = [k for k, v in self._challenges.items() if now > v.expires_at]
        for k in expired_keys:
            self._challenges.pop(k, None)

    def prune_expired(self) -> int:
        """Explicitly prune expired records and return count of pruned entries."""
        with self._lock:
            now = int(time.time())
            expired_keys = [k for k, v in self._challenges.items() if now > v.expires_at]
            for k in expired_keys:
                self._challenges.pop(k, None)
            return len(expired_keys)

    def clear(self) -> None:
        """Clear all active challenges (used for test teardown)."""
        with self._lock:
            self._challenges.clear()


# Default singleton instance for the process
default_nonce_store = NonceStore()


# ---------------------------------------------------------------------------
# Session Bearer Token Manager (HMAC-SHA256)
# ---------------------------------------------------------------------------


class SessionTokenManager:
    """Manages creation and verification of signed session bearer tokens."""

    @staticmethod
    def create_session_token(
        account: str,
        secret_key: str,
        ttl_seconds: int = 86400,
        extra_claims: Optional[dict[str, Any]] = None,
    ) -> str:
        """Generate a cryptographically signed URL-safe bearer token."""
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": account,
            "iat": now,
            "exp": now + ttl_seconds,
            "jti": secrets.token_hex(16),
        }
        if extra_claims:
            payload.update(extra_claims)

        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii").rstrip("=")

        sig = hmac.new(
            secret_key.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")

        return f"{payload_b64}.{sig_b64}"

    @staticmethod
    def verify_session_token(token: str, secret_key: str) -> dict[str, Any]:
        """Verify token signature and expiration in constant time.

        Raises ValueError on malformed, tampered, or expired tokens.
        """
        parts = token.strip().split(".")
        if len(parts) != 2:
            raise ValueError("Malformed session token: expected '<payload>.<signature>'.")

        payload_b64, sig_b64 = parts

        # Constant-time signature verification
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")

        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            raise ValueError("Session token signature verification failed.")

        # Decode payload
        rem = len(payload_b64) % 4
        padded_b64 = payload_b64 + ("=" * ((4 - rem) % 4))
        try:
            payload_json = base64.urlsafe_b64decode(padded_b64).decode("utf-8")
            payload = json.loads(payload_json)
        except Exception as exc:
            raise ValueError(f"Corrupted session token payload: {exc}") from exc

        now = int(time.time())
        if "exp" in payload and now > payload["exp"]:
            raise ValueError(
                f"Session token has expired (now={now}, exp={payload['exp']})."
            )

        if "sub" not in payload or not payload["sub"]:
            raise ValueError("Session token is missing subject ('sub') claim.")

        return payload
