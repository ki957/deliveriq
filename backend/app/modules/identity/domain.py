"""Identity rules: mobile normalisation, OTP/session policy and login eligibility (DDR-96–DDR-98).

Standard library plus the core permission catalogue; no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.core.permissions import PORTAL_ROLES, Portal, Role

# ---------------------------------------------------------------- policy values (DDR-96, DDR-98)
OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 30
OTP_MOBILE_LIMIT = 5
OTP_IP_LIMIT = 20
OTP_WINDOW_SECONDS = 15 * 60
OTP_LOCKOUT_SECONDS = 15 * 60
SESSION_IDLE_SECONDS = 2 * 60 * 60
SESSION_ABSOLUTE_SECONDS = 24 * 60 * 60
TRUSTED_DEVICE_SECONDS = 7 * 24 * 60 * 60
NAME_MAX_CHARS = 80

# ---------------------------------------------------------------- mobile numbers (DDR-96)
INDIA_MOBILE = re.compile(r"\+91[6-9]\d{9}")
# #15 §4 placeholder range (+91-00000-0000x): never a real Indian mobile; local/test only.
TEST_MOBILE = re.compile(r"\+9100000\d{5}")
_SEPARATORS = re.compile(r"[\s\-().]")


def normalize_mobile(raw: str, *, allow_test_numbers: bool) -> str | None:
    """Return E.164 (`+91XXXXXXXXXX`) or None if the number is not an accepted Indian mobile."""
    value = _SEPARATORS.sub("", raw.strip())
    if re.fullmatch(r"\d{10}", value):
        value = "+91" + value
    elif re.fullmatch(r"91\d{10}", value):
        value = "+" + value
    if INDIA_MOBILE.fullmatch(value):
        return value
    if allow_test_numbers and TEST_MOBILE.fullmatch(value):
        return value
    return None


def mask_mobile(mobile: str) -> str:
    """For audit records: never store a full mobile number outside app.users."""
    return mobile[:3] + "*" * (len(mobile) - 5) + mobile[-2:]


# ---------------------------------------------------------------- login eligibility (DDR-97)
class LoginDecision(StrEnum):
    ALLOW = "allow"
    REGISTER = "register"  # new customer: create account after OTP verification
    DENY = "deny"


@dataclass(frozen=True)
class UserState:
    status: str
    roles: frozenset[Role]


def login_decision(portal: Portal, user: UserState | None) -> LoginDecision:
    if user is None:
        # Only the customer portal self-registers; staff are provisioned (DDR-97).
        return LoginDecision.REGISTER if portal is Portal.CUSTOMER else LoginDecision.DENY
    if user.status != "ACTIVE":
        return LoginDecision.DENY
    # PL-03: the Customer role is never implied for staff.
    return LoginDecision.ALLOW if user.roles & PORTAL_ROLES[portal] else LoginDecision.DENY


def clean_display_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    name = " ".join(raw.split())
    return name if 1 <= len(name) <= NAME_MAX_CHARS else None
