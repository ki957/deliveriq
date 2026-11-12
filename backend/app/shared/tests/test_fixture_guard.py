"""Production startup refuses TEST fixture rows (plan §5.2 control 3). DB-level proof is in the
pipelines/recipes integration tests; here the decision logic is checked with a stub connection."""

from __future__ import annotations

from typing import Any

import pytest

from app.shared import fixture_guard

pytestmark = pytest.mark.unit


class _Result:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class _Conn:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts

    def execute(self, statement: Any) -> _Result:
        sql = str(statement)
        table = "ingredients" if "origin" in sql else sql.split("FROM app.")[1].split()[0]
        return _Result(self.counts.get(table, 0))


def test_clean_database_passes() -> None:
    fixture_guard.assert_no_fixtures(_Conn({}))  # type: ignore[arg-type]


@pytest.mark.parametrize("table", [*fixture_guard.FIXTURE_TABLES, "ingredients"])
def test_any_fixture_row_blocks_startup(table: str) -> None:
    with pytest.raises(fixture_guard.FixtureRowsPresent, match=f"{table}=2"):
        fixture_guard.assert_no_fixtures(_Conn({table: 2}))  # type: ignore[arg-type]
