from __future__ import annotations

import pytest

from app.modules.identity import domain as d
from app.modules.identity.rate_limit import OtpLimiter, RateLimited

pytestmark = pytest.mark.unit


class FakeRedis:
    """Minimal in-memory stand-in for the Redis calls the limiter uses (no expiry clock)."""

    def __init__(self) -> None:
        self.data: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def set(self, name: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool | None:
        if nx and name in self.data:
            return None
        self.data[name] = 1
        if ex is not None:
            self.ttls[name] = ex
        return True

    def incr(self, name: str) -> int:
        self.data[name] = self.data.get(name, 0) + 1
        return self.data[name]

    def expire(self, name: str, time: int) -> bool:
        self.ttls[name] = time
        return True

    def ttl(self, name: str) -> int:
        return self.ttls.get(name, -1)

    def exists(self, *names: str) -> int:
        return sum(n in self.data for n in names)

    def delete(self, *names: str) -> int:
        return sum(self.data.pop(n, None) is not None for n in names)

    def clear_cooldowns(self) -> None:
        for key in [k for k in self.data if k.startswith("otp:cooldown")]:
            del self.data[key]


MOBILE = "+919876543210"


def test_resend_cooldown_applies_per_mobile_and_portal() -> None:
    limiter = OtpLimiter(FakeRedis())
    limiter.register_request(MOBILE, "customer", "1.1.1.1")
    with pytest.raises(RateLimited) as limited:
        limiter.register_request(MOBILE, "customer", "1.1.1.1")
    assert limited.value.retry_after == d.OTP_RESEND_COOLDOWN_SECONDS
    limiter.register_request(MOBILE, "kitchen", "1.1.1.1")  # different portal, own cooldown


def test_mobile_limit_then_lockout() -> None:
    redis = FakeRedis()
    limiter = OtpLimiter(redis)
    for _ in range(d.OTP_MOBILE_LIMIT):
        limiter.register_request(MOBILE, "customer", "1.1.1.1")
        redis.clear_cooldowns()
    with pytest.raises(RateLimited) as limited:
        limiter.register_request(MOBILE, "customer", "1.1.1.1")
    assert limited.value.retry_after == d.OTP_LOCKOUT_SECONDS
    with pytest.raises(RateLimited):
        limiter.ensure_not_locked(MOBILE)


def test_ip_limit_covers_many_numbers() -> None:
    limiter = OtpLimiter(FakeRedis())
    for i in range(d.OTP_IP_LIMIT):
        limiter.register_request(f"+91987654{i:04d}", "customer", "2.2.2.2")
    with pytest.raises(RateLimited):
        limiter.register_request("+919999999999", "customer", "2.2.2.2")
    # Another IP is unaffected (fresh number: the blocked one has started its resend cooldown).
    limiter.register_request("+919999999998", "customer", "3.3.3.3")


def test_keys_contain_no_raw_mobile() -> None:
    redis = FakeRedis()
    OtpLimiter(redis).register_request(MOBILE, "customer", "1.1.1.1")
    assert redis.data
    assert all("9876543210" not in key for key in redis.data)
