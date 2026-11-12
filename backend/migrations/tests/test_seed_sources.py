"""Leak control 5 (plan §5.2): production seed files contain no fixture rows.

Checked on the migration sources, not the live database: once `make fixtures` has loaded the TEST
menu (local/test), the database legitimately holds fixture rows that no migration created.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

VERSIONS = Path(__file__).resolve().parents[1] / "versions"
FIXTURE_TABLES = ("menu_items", "recipe_versions", "orders", "order_items", "payments")


def _upgrade_sources() -> dict[str, str]:
    sources = {}
    for path in sorted(VERSIONS.glob("[0-9]*.py")):
        text = path.read_text(encoding="utf-8")
        # Downgrade SQL may name fixture tables in DROP statements; only upgrade content matters.
        sources[path.name] = text.split("DOWNGRADE_SQL")[0].split("REVOKE_SQL")[0]
    return sources


def test_migrations_exist() -> None:
    assert len(_upgrade_sources()) >= 7


@pytest.mark.parametrize("name", sorted(_upgrade_sources()))
def test_no_migration_seeds_fixture_rows(name: str) -> None:
    text = _upgrade_sources()[name]
    for table in FIXTURE_TABLES:
        assert not re.search(rf"INSERT\s+INTO\s+app\.{table}\b", text, re.IGNORECASE), (
            f"{name} seeds app.{table}"
        )
    # Recipe and menu master data come only from P1 (real) or the local/test loader (TEST).
    assert not re.search(
        r"INSERT\s+INTO\s+app\.(ingredients|recipes|menu_categories)\b", text, re.IGNORECASE
    ), name
