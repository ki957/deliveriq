"""The E2E second-region fixture (DDR-114 (14)) stays inside the TEST conventions."""

from __future__ import annotations

import re

from app.cli import fixtures as fx


def test_second_region_codes_are_valid_and_never_collide_with_the_integration_world() -> None:
    region_code, _ = fx.E2E_REGION
    kitchen_code, _ = fx.E2E_KITCHEN
    # Migration 0001 code formats.
    assert re.fullmatch(r"REG-[A-Z]{3}-[0-9]{3}", region_code)
    assert re.fullmatch(r"KIT-[A-Z]{3}-[0-9]{3}", kitchen_code)
    # The integration world creates REG-TST-nnn / KIT-TST-nnn and deletes them afterwards.
    assert not region_code.startswith("REG-TST-")
    assert not kitchen_code.startswith("KIT-TST-")
    # The customer portal serves the first ACTIVE kitchen by code; the seed kitchen must stay first.
    assert kitchen_code > "KIT-CHN-001"


def test_second_region_names_carry_the_test_prefix_and_the_mobile_is_unique() -> None:
    assert fx.E2E_REGION[1].startswith("TEST – ")
    assert fx.E2E_KITCHEN[1].startswith("TEST – ")
    name, mobile = fx.E2E_REGIONAL_MANAGER
    assert name.startswith("TEST – ")
    # The #15 placeholder range, accepted only in local/test.
    assert re.fullmatch(r"\+9100000000[0-9]{2}", mobile)
    taken = {m for _, m, *_ in fx.SEED_USERS} | {fx.E2E_AGENT[1]}
    assert mobile not in taken
