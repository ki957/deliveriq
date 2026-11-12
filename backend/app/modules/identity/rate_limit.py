"""OTP request limits in Redis (DDR-96). Redis errors propagate: OTP fails closed (DDR-98).

Fixed-window counters per mobile and per IP; a resend cooldown per mobile+portal; a lockout per
mobile once a limit is exceeded or a code's attempts run out. Keys hold no raw mobile numbers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from app.modules.identity import domain as d


class RedisLike(Protocol):
    def set(self, name: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool | None: ...
    def incr(self, name: str) -> int: ...
    def expire(self, name: str, time: int) -> bool: ...
    def ttl(self, name: str) -> int: ...
    def exists(self, *names: str) -> int: ...
    def delete(self, *names: str) -> int: ...


class RateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("rate limited")
        self.retry_after = max(retry_after, 1)


def _key(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:32]
    return f"otp:{parts[0]}:{digest}"


@dataclass
class OtpLimiter:
    redis: RedisLike

    def _lock_key(self, mobile: str) -> str:
        return _key("lock", mobile)

    def ensure_not_locked(self, mobile: str) -> None:
        key = self._lock_key(mobile)
        if self.redis.exists(key):
            raise RateLimited(self.redis.ttl(key))

    def lock(self, mobile: str) -> None:
        self.redis.set(self._lock_key(mobile), "1", ex=d.OTP_LOCKOUT_SECONDS)

    def _count(self, key: str) -> int:
        count = self.redis.incr(key)
        if count == 1:
            self.redis.expire(key, d.OTP_WINDOW_SECONDS)
        return count

    def register_request(self, mobile: str, portal: str, ip: str) -> None:
        """Apply cooldown and window limits to every request, eligible or not (no enumeration)."""
        self.ensure_not_locked(mobile)
        cooldown = _key("cooldown", mobile, portal)
        if not self.redis.set(cooldown, "1", ex=d.OTP_RESEND_COOLDOWN_SECONDS, nx=True):
            raise RateLimited(self.redis.ttl(cooldown))
        if self._count(_key("ip", ip)) > d.OTP_IP_LIMIT:
            raise RateLimited(self.redis.ttl(_key("ip", ip)))
        if self._count(_key("mobile", mobile)) > d.OTP_MOBILE_LIMIT:
            self.lock(mobile)
            raise RateLimited(d.OTP_LOCKOUT_SECONDS)
