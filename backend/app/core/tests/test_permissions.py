"""Negative matrix at the policy level (Phase 2 §8.5; plan Task 4). HTTP-level proof is in
identity/tests/test_auth_integration.py."""

from __future__ import annotations

import uuid

import pytest

from app.core.permissions import ROLE_PERMISSIONS, Grant, Permission, Portal, Principal, Role, can

pytestmark = pytest.mark.unit
P = Permission

REGION_A, REGION_B = uuid.uuid4(), uuid.uuid4()
KITCHEN_A, KITCHEN_B = uuid.uuid4(), uuid.uuid4()


def principal(role: Role, *, region: uuid.UUID | None = None, kitchen: uuid.UUID | None = None) -> Principal:
    return Principal(uuid.uuid4(), (Grant(role, region, kitchen),))


def test_customer_sees_only_own_data() -> None:
    me = principal(Role.CUSTOMER)
    assert can(me, P.CUSTOMER_ORDERS_READ, customer_id=me.user_id)
    assert not can(me, P.CUSTOMER_ORDERS_READ, customer_id=uuid.uuid4())
    assert not can(me, P.CUSTOMER_ORDERS_READ)  # no scope given: deny


def test_kitchen_roles_are_bound_to_their_kitchen() -> None:
    staff = principal(Role.KITCHEN_STAFF, region=REGION_A, kitchen=KITCHEN_A)
    assert can(staff, P.KITCHEN_ORDERS_VIEW, kitchen_id=KITCHEN_A)
    assert not can(staff, P.KITCHEN_ORDERS_VIEW, kitchen_id=KITCHEN_B)


@pytest.mark.parametrize(
    "permission",
    [P.KITCHEN_RECIPES_EDIT, P.KITCHEN_RECIPES_ACTIVATE, P.KITCHEN_STOCK_ADJUST, P.KITCHEN_MODE_CHANGE,
     P.KITCHEN_INGREDIENTS_MANAGE, P.KITCHEN_ETA_UPDATE, P.KITCHEN_INVENTORY_VIEW,
     P.KITCHEN_ORDERS_REJECT_ACCEPTED],
)  # fmt: skip
def test_kitchen_staff_cannot_use_manager_only_actions(permission: Permission) -> None:
    staff = principal(Role.KITCHEN_STAFF, region=REGION_A, kitchen=KITCHEN_A)
    manager = principal(Role.KITCHEN_MANAGER, region=REGION_A, kitchen=KITCHEN_A)
    assert not can(staff, permission, kitchen_id=KITCHEN_A)
    assert can(manager, permission, kitchen_id=KITCHEN_A)


def test_regional_manager_is_bound_to_assigned_region() -> None:
    rm = principal(Role.REGIONAL_MANAGER, region=REGION_A)
    assert can(rm, P.MENU_PUBLISH, region_id=REGION_A)
    assert not can(rm, P.MENU_PUBLISH, region_id=REGION_B)


@pytest.mark.parametrize("permission", [P.MGMT_RM_MANAGE, P.MGMT_GLOBAL_SETTINGS, P.MGMT_REFUND_OVERRIDE,
                                        P.MGMT_AUDIT_GLOBAL])  # fmt: skip
def test_regional_manager_cannot_use_central_admin_actions(permission: Permission) -> None:
    rm = principal(Role.REGIONAL_MANAGER, region=REGION_A)
    ca = principal(Role.CENTRAL_ADMIN)
    assert not can(rm, permission, region_id=REGION_A)
    assert can(ca, permission)


def test_central_admin_is_global_but_only_for_its_permissions() -> None:
    ca = principal(Role.CENTRAL_ADMIN)
    assert can(ca, P.MENU_PUBLISH, region_id=REGION_B)
    assert not can(ca, P.KITCHEN_RECIPES_ACTIVATE, kitchen_id=KITCHEN_A)  # KM only (DDR-30)
    assert not can(ca, P.CUSTOMER_ORDERS_READ, customer_id=uuid.uuid4())


def test_publication_authority_matches_ddr_31() -> None:
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if P.MENU_PUBLISH in perms}
    assert holders == {Role.REGIONAL_MANAGER, Role.CENTRAL_ADMIN}


def test_only_kitchen_manager_activates_recipes() -> None:
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if P.KITCHEN_RECIPES_ACTIVATE in perms}
    assert holders == {Role.KITCHEN_MANAGER}


def test_staff_do_not_get_customer_portal() -> None:
    assert principal(Role.KITCHEN_MANAGER, region=REGION_A, kitchen=KITCHEN_A).portals() == [Portal.KITCHEN]
    multi = Principal(uuid.uuid4(), (Grant(Role.CUSTOMER), Grant(Role.REGIONAL_MANAGER, REGION_A)))
    assert multi.portals() == [Portal.CUSTOMER, Portal.MANAGEMENT]


def test_pipeline_permissions_match_ddr_105() -> None:
    """CA views and operates every run; RM views own region only; everyone else is denied."""
    view = {role for role, perms in ROLE_PERMISSIONS.items() if P.PIPELINES_VIEW in perms}
    operate = {role for role, perms in ROLE_PERMISSIONS.items() if P.PIPELINES_OPERATE in perms}
    assert view == {Role.REGIONAL_MANAGER, Role.CENTRAL_ADMIN}
    assert operate == {Role.CENTRAL_ADMIN}
    rm = principal(Role.REGIONAL_MANAGER, region=REGION_A)
    assert can(rm, P.PIPELINES_VIEW, region_id=REGION_A)
    assert not can(rm, P.PIPELINES_VIEW, region_id=REGION_B)
    assert not can(rm, P.PIPELINES_VIEW)  # runs without a region are CA-only
    assert not can(rm, P.PIPELINES_OPERATE, region_id=REGION_A)
    assert can(principal(Role.CENTRAL_ADMIN), P.PIPELINES_OPERATE, region_id=REGION_B)


def test_recipe_workflow_permissions_match_ddr_105_and_106() -> None:
    def holders(permission: Permission) -> set[Role]:
        return {role for role, perms in ROLE_PERMISSIONS.items() if permission in perms}

    assert holders(P.KITCHEN_RECIPES_WORKFLOW) == {Role.KITCHEN_MANAGER}
    assert holders(P.KITCHEN_RECIPES_SIGNOFF) == {Role.KITCHEN_MANAGER}
    assert holders(P.KITCHEN_REVIEW_ACKNOWLEDGE) == {Role.KITCHEN_MANAGER}
    assert holders(P.KITCHEN_REVIEW_VIEW) == {Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER}
    assert holders(P.RECIPES_PRODUCT_OWNER_SIGNOFF) == {Role.CENTRAL_ADMIN}
    km = principal(Role.KITCHEN_MANAGER, region=REGION_A, kitchen=KITCHEN_A)
    assert can(km, P.KITCHEN_RECIPES_WORKFLOW, kitchen_id=KITCHEN_A)
    assert not can(km, P.KITCHEN_RECIPES_WORKFLOW, kitchen_id=KITCHEN_B)


def test_only_customers_place_and_cancel_their_own_orders() -> None:
    for permission in (P.CUSTOMER_ORDERS_PLACE, P.CUSTOMER_ORDERS_CANCEL):
        assert {r for r, perms in ROLE_PERMISSIONS.items() if permission in perms} == {Role.CUSTOMER}
    me = principal(Role.CUSTOMER)
    assert can(me, P.CUSTOMER_ORDERS_PLACE, customer_id=me.user_id)
    assert not can(me, P.CUSTOMER_ORDERS_CANCEL, customer_id=uuid.uuid4())


def test_only_customers_manage_their_own_addresses() -> None:
    holders = {r for r, perms in ROLE_PERMISSIONS.items() if P.CUSTOMER_ADDRESSES_MANAGE in perms}
    assert holders == {Role.CUSTOMER}
    me = principal(Role.CUSTOMER)
    assert can(me, P.CUSTOMER_ADDRESSES_MANAGE, customer_id=me.user_id)
    assert not can(me, P.CUSTOMER_ADDRESSES_MANAGE, customer_id=uuid.uuid4())


def test_kitchen_operations_authority_matches_ddr_111() -> None:
    """Low-stock alerts for both kitchen roles, full stock for KM; post-acceptance reject for KM/RM/CA."""
    staff = principal(Role.KITCHEN_STAFF, region=REGION_A, kitchen=KITCHEN_A)
    rm = principal(Role.REGIONAL_MANAGER, region=REGION_A)
    assert can(staff, P.KITCHEN_LOW_STOCK_VIEW, kitchen_id=KITCHEN_A)
    assert can(staff, P.KITCHEN_UNAVAILABILITY_REQUEST, kitchen_id=KITCHEN_A)
    assert not can(staff, P.MGMT_UNAVAILABILITY_APPROVE, region_id=REGION_A)
    assert can(rm, P.KITCHEN_ORDERS_REJECT_ACCEPTED, region_id=REGION_A)
    assert not can(rm, P.KITCHEN_ORDERS_REJECT_ACCEPTED, region_id=REGION_B)
    assert can(principal(Role.CENTRAL_ADMIN), P.KITCHEN_ORDERS_REJECT_ACCEPTED, region_id=REGION_B)
    assert not can(rm, P.KITCHEN_ORDERS_PROCESS, region_id=REGION_A)  # RM does not run the line
    assert not can(principal(Role.DELIVERY_AGENT, region=REGION_A), P.KITCHEN_ORDERS_VIEW, region_id=REGION_A)


def test_management_inventory_view_is_read_only_and_scoped() -> None:
    rm = principal(Role.REGIONAL_MANAGER, region=REGION_A)
    assert can(rm, P.MGMT_INVENTORY_VIEW, region_id=REGION_A)
    assert not can(rm, P.MGMT_INVENTORY_VIEW, region_id=REGION_B)
    assert not can(rm, P.KITCHEN_STOCK_ADJUST, kitchen_id=KITCHEN_A)  # management never adjusts stock
    assert not can(principal(Role.KITCHEN_MANAGER, region=REGION_A, kitchen=KITCHEN_A), P.MGMT_INVENTORY_VIEW,
                   region_id=REGION_A)  # fmt: skip


def test_management_reports_are_scoped_to_rm_regions_and_global_for_ca() -> None:
    rm = principal(Role.REGIONAL_MANAGER, region=REGION_A)
    assert can(rm, P.MGMT_REPORTS_VIEW, region_id=REGION_A)
    assert not can(rm, P.MGMT_REPORTS_VIEW, region_id=REGION_B)
    assert not can(rm, P.MGMT_REPORTS_VIEW)  # an RM has no global grant
    assert can(principal(Role.CENTRAL_ADMIN), P.MGMT_REPORTS_VIEW)
    for role in (Role.KITCHEN_MANAGER, Role.KITCHEN_STAFF, Role.DELIVERY_AGENT, Role.CUSTOMER):
        assert P.MGMT_REPORTS_VIEW not in ROLE_PERMISSIONS[role]
