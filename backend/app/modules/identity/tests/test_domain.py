from __future__ import annotations

import pytest

from app.core.permissions import Portal, Role
from app.modules.identity.domain import (
    LoginDecision,
    UserState,
    clean_display_name,
    login_decision,
    mask_mobile,
    normalize_mobile,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+91 98765 43210", "+919876543210"),
        ("9876543210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+91-98765-43210", "+919876543210"),
        ("(+91) 6000000000", "+916000000000"),
        ("5876543210", None),  # Indian mobiles start 6-9
        ("+1 415 555 0100", None),  # India only (DDR-96)
        ("98765", None),
        ("+91-00000-00001", None),  # #15 placeholder: rejected outside local/test
    ],
)
def test_normalize_mobile_production(raw: str, expected: str | None) -> None:
    assert normalize_mobile(raw, allow_test_numbers=False) == expected


def test_placeholder_numbers_accepted_only_in_local_test() -> None:
    assert normalize_mobile("+91-00000-00001", allow_test_numbers=True) == "+910000000001"
    assert normalize_mobile("+91-00000-00001", allow_test_numbers=False) is None


def test_mask_mobile_keeps_country_code_and_last_two_digits() -> None:
    assert mask_mobile("+919876543210") == "+91********10"


def _state(*roles: Role, status: str = "ACTIVE") -> UserState:
    return UserState(status, frozenset(roles))


def test_unknown_number_registers_only_at_customer_portal() -> None:
    assert login_decision(Portal.CUSTOMER, None) is LoginDecision.REGISTER
    for portal in (Portal.KITCHEN, Portal.DELIVERY, Portal.MANAGEMENT):
        assert login_decision(portal, None) is LoginDecision.DENY


def test_staff_without_customer_role_cannot_log_in_as_customer() -> None:
    assert login_decision(Portal.CUSTOMER, _state(Role.KITCHEN_STAFF)) is LoginDecision.DENY
    assert login_decision(Portal.KITCHEN, _state(Role.KITCHEN_STAFF)) is LoginDecision.ALLOW


def test_inactive_users_are_denied_everywhere() -> None:
    for status in ("SUSPENDED", "DEACTIVATED"):
        assert login_decision(Portal.CUSTOMER, _state(Role.CUSTOMER, status=status)) is LoginDecision.DENY


def test_portal_requires_a_matching_role() -> None:
    assert login_decision(Portal.MANAGEMENT, _state(Role.KITCHEN_MANAGER)) is LoginDecision.DENY
    assert login_decision(Portal.MANAGEMENT, _state(Role.CENTRAL_ADMIN)) is LoginDecision.ALLOW


@pytest.mark.parametrize(
    ("raw", "expected"), [("  Asha   R ", "Asha R"), ("", None), ("x" * 81, None), (None, None)]
)
def test_clean_display_name(raw: str | None, expected: str | None) -> None:
    assert clean_display_name(raw) == expected
