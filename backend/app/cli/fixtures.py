"""Local/test fixture loader (plan §5.2 control 2; DDR-99).

    docker compose --project-directory . -f infra/compose.yaml --profile core \\
        run --rm migrate python -m app.cli.fixtures load-users

Loads the six #15 §4 seed users and role assignments (`load-users`), the TEST menu
(`load-menu`, see `fixtures_menu.py`) and the TEST opening stock (`load-stock`, DDR-37); `load-all`
does all three; `reset-shared` restores the shared TEST baseline. Their mobile numbers are the
#15 placeholder range, accepted only in local/test. Refuses to run unless APP_ENV is local or
test. Idempotent.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine

# (display_name, mobile, role, region_code, kitchen_code) from #15 §4 and §4.1.
SEED_USERS: tuple[tuple[str, str, str, str | None, str | None], ...] = (
    ("Demo Customer", "+910000000001", "CUSTOMER", None, None),
    ("Demo Delivery Agent", "+910000000002", "DELIVERY_AGENT", "REG-CHN-001", None),
    ("Demo Kitchen Staff", "+910000000003", "KITCHEN_STAFF", "REG-CHN-001", "KIT-CHN-001"),
    ("Demo Kitchen Manager", "+910000000004", "KITCHEN_MANAGER", "REG-CHN-001", "KIT-CHN-001"),
    ("Demo Regional Manager", "+910000000005", "REGIONAL_MANAGER", "REG-CHN-001", None),
    ("Demo Central Administrator", "+910000000006", "CENTRAL_ADMIN", None, None),
)


# E2E only (loaded by `make e2e-setup`): a TEST delivery agent for the delivery flow spec, so it never
# competes with the seed agent used by the read-only screen checks. Local/test only.
E2E_AGENT = ("TEST – E2E Delivery Agent", "+910000000007", "REG-CHN-001")

# #15 §5 ADR-CUS-001 (address line, latitude, longitude): synthetic test values.
SEED_ADDRESS = ("Synthetic Test Address, Chennai, Tamil Nadu, India", 13.0835, 80.2710)


def load_users() -> int:
    created = 0
    with get_engine().begin() as conn:
        for name, mobile, role, region_code, kitchen_code in SEED_USERS:
            user_id = conn.execute(
                text(
                    "INSERT INTO app.users (display_name, mobile_e164) VALUES (:n, :m) "
                    "ON CONFLICT (mobile_e164) DO UPDATE SET display_name = EXCLUDED.display_name "
                    "RETURNING id"
                ),
                {"n": name, "m": mobile},
            ).scalar_one()
            result = conn.execute(
                text(
                    "INSERT INTO app.role_assignments (user_id, role, region_id, kitchen_id) "
                    "SELECT :u, :role, (SELECT id FROM app.regions WHERE code = :rc), "
                    "       (SELECT id FROM app.kitchens WHERE code = :kc) "
                    "WHERE NOT EXISTS (SELECT 1 FROM app.role_assignments "
                    "                  WHERE user_id = :u AND role = :role AND revoked_at IS NULL)"
                ),
                {"u": user_id, "role": role, "rc": region_code, "kc": kitchen_code},
            )
            created += result.rowcount
        # #15 §5: ADR-CUS-001, the seed customer's default address (synthetic coordinates).
        conn.execute(
            text(
                "INSERT INTO app.customer_addresses "
                "(customer_user_id, label, address_line, location, is_default) "
                "SELECT u.id, 'Home', :a, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, true "
                "FROM app.users u WHERE u.mobile_e164 = :m AND NOT EXISTS "
                "(SELECT 1 FROM app.customer_addresses x "
                "WHERE x.customer_user_id = u.id AND x.deleted_at IS NULL)"
            ),
            {"a": SEED_ADDRESS[0], "lat": SEED_ADDRESS[1], "lng": SEED_ADDRESS[2], "m": SEED_USERS[0][1]},
        )
    return created


def load_e2e_agent() -> None:
    name, mobile, region = E2E_AGENT
    with get_engine().begin() as conn:
        user_id = conn.execute(
            text(
                "INSERT INTO app.users (display_name, mobile_e164) VALUES (:n, :m) "
                "ON CONFLICT (mobile_e164) DO UPDATE SET display_name = EXCLUDED.display_name RETURNING id"
            ),
            {"n": name, "m": mobile},
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO app.role_assignments (user_id, role, region_id) "
                "SELECT :u, 'DELIVERY_AGENT', (SELECT id FROM app.regions WHERE code = :rc) "
                "WHERE NOT EXISTS (SELECT 1 FROM app.role_assignments WHERE user_id = :u "
                "AND role = 'DELIVERY_AGENT' AND revoked_at IS NULL)"
            ),
            {"u": user_id, "rc": region},
        )
        # Start each run offline: the spec goes online itself.
        conn.execute(
            text("UPDATE app.agent_availability SET status = 'OFFLINE' WHERE agent_user_id = :u"),
            {"u": user_id},
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load local/test fixtures")
    parser.add_argument(
        "command",
        choices=[
            "load-users",
            "load-menu",
            "load-stock",
            "load-all",
            "load-e2e-recipe",
            "load-e2e-agent",
            "reset-shared",
        ],
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    if not settings.is_local_or_test:
        print("refused: fixtures load only when APP_ENV is local or test", file=sys.stderr)
        return 2
    if args.command in ("load-users", "load-all"):
        created = load_users()
        print(f"seed users ready ({len(SEED_USERS)}); role grants created: {created}")
    if args.command == "load-e2e-agent":
        load_e2e_agent()
        print("E2E delivery agent ready (TEST, offline)")
        return 0
    if args.command == "reset-shared":
        from app.cli.fixtures_menu import reset_shared

        print("shared TEST state reset: " + ", ".join(f"{k}={v}" for k, v in reset_shared().items()))
        return 0
    if args.command == "load-e2e-recipe":
        from app.cli.fixtures_menu import load_e2e_recipe

        print(f"E2E recipe ready: {load_e2e_recipe()}")
        return 0
    if args.command in ("load-menu", "load-all"):
        from app.cli.fixtures_menu import load_menu

        summary = load_menu()
        print("TEST menu ready: " + ", ".join(f"{k}={v}" for k, v in summary.items()))
    if args.command in ("load-stock", "load-all"):
        from app.cli.fixtures_menu import load_stock

        print(f"TEST opening stock ready (test-only, DDR-37): rows added={load_stock()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
