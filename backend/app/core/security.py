"""Token and OTP hashing. Plain codes and tokens are never stored or logged (PL-02, PL-13)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

TOKEN_BYTES = 32


def new_token() -> str:
    """High-entropy opaque token for session and trusted-device cookies (DDR-98)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    """SHA-256 is sufficient for 256-bit random tokens; only this hash is stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def otp_hash(code: str, *, mobile: str, pepper: str) -> str:
    """Keyed hash: a 6-digit space is small, so a plain hash could be brute-forced offline."""
    return hmac.new(pepper.encode(), f"{mobile}:{code}".encode(), hashlib.sha256).hexdigest()


def hashes_match(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def new_otp_code(length: int) -> str:
    return f"{secrets.randbelow(10**length):0{length}d}"
