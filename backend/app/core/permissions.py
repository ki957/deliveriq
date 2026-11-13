"""Role → permission catalogue and scope checks (DDR-99; Matrix §3.1, §5.1; Phase 2 §8).

Pure code, no I/O. Deny by default: a permission is granted only when a role grant includes it
AND the grant's scope covers the resource. The backend is the security boundary; the UI only
mirrors `GET /api/v1/me` permissions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "CUSTOMER"
    DELIVERY_AGENT = "DELIVERY_AGENT"
    KITCHEN_STAFF = "KITCHEN_STAFF"
    KITCHEN_MANAGER = "KITCHEN_MANAGER"
    REGIONAL_MANAGER = "REGIONAL_MANAGER"
    CENTRAL_ADMIN = "CENTRAL_ADMIN"


class Portal(StrEnum):
    CUSTOMER = "customer"
    KITCHEN = "kitchen"
    DELIVERY = "delivery"
    MANAGEMENT = "management"


PORTAL_ROLES: dict[Portal, frozenset[Role]] = {
    Portal.CUSTOMER: frozenset({Role.CUSTOMER}),
    Portal.KITCHEN: frozenset({Role.KITCHEN_STAFF, Role.KITCHEN_MANAGER}),
    Portal.DELIVERY: frozenset({Role.DELIVERY_AGENT}),
    Portal.MANAGEMENT: frozenset({Role.REGIONAL_MANAGER, Role.CENTRAL_ADMIN}),
}


class Permission(StrEnum):
    # Customer (own data only)
    CUSTOMER_PROFILE_READ = "customer.profile.read"
    CUSTOMER_ORDERS_READ = "customer.orders.read"
    # Own orders only (DDR-109)
    CUSTOMER_ORDERS_PLACE = "customer.orders.place"
    CUSTOMER_ORDERS_CANCEL = "customer.orders.cancel"
    # Saved delivery addresses (CU-02)
    CUSTOMER_ADDRESSES_MANAGE = "customer.addresses.manage"
    # Kitchen (Matrix §3.1)
    KITCHEN_ORDERS_VIEW = "kitchen.orders.view"
    KITCHEN_ORDERS_PROCESS = "kitchen.orders.process"
    KITCHEN_RECIPES_VIEW = "kitchen.recipes.view"
    KITCHEN_RECIPES_EDIT = "kitchen.recipes.edit"
    KITCHEN_RECIPES_ACTIVATE = "kitchen.recipes.activate"
    KITCHEN_INGREDIENTS_MANAGE = "kitchen.ingredients.manage"
    KITCHEN_STOCK_ADJUST = "kitchen.stock.adjust"
    KITCHEN_LOW_STOCK_VIEW = "kitchen.low_stock.view"
    KITCHEN_MODE_CHANGE = "kitchen.mode.change"
    KITCHEN_ETA_UPDATE = "kitchen.eta.update"
    KITCHEN_UNAVAILABILITY_REQUEST = "kitchen.unavailability.request"
    # Recipe workflow (DDR-10, DDR-54, DDR-103, DDR-105, DDR-107): KM submits, returns, validates,
    # rejects and activates; KM records four sign-offs; KS and KM view the review queue; KM acknowledges.
    KITCHEN_RECIPES_WORKFLOW = "kitchen.recipes.workflow"
    KITCHEN_RECIPES_SIGNOFF = "kitchen.recipes.signoff"
    KITCHEN_REVIEW_VIEW = "kitchen.review.view"
    KITCHEN_REVIEW_ACKNOWLEDGE = "kitchen.review.acknowledge"
    # Delivery
    DELIVERY_ASSIGNMENTS_VIEW = "delivery.assignments.view"
    # Management (Matrix §5.1)
    MGMT_OPERATIONS_VIEW = "management.operations.view"
    MGMT_STAFF_MANAGE = "management.staff.manage"
    MGMT_RM_MANAGE = "management.regional_managers.manage"
    MGMT_AGENTS_ASSIGN = "management.agents.assign"
    MGMT_UNAVAILABILITY_APPROVE = "management.unavailability.approve"
    MGMT_REFUND_EXCEPTIONAL = "management.refunds.exceptional_approve"
    MGMT_REFUND_OVERRIDE = "management.refunds.override"
    MGMT_REGIONAL_SETTINGS = "management.settings.regional"
    MGMT_GLOBAL_SETTINGS = "management.settings.global"
    MGMT_AUDIT_REGIONAL = "management.audit.regional"
    MGMT_AUDIT_GLOBAL = "management.audit.global"
    MENU_PUBLISH = "menu.publish"
    # Data & Pipelines (DDR-106): CA everywhere, RM own region (view only)
    PIPELINES_VIEW = "pipelines.view"
    PIPELINES_OPERATE = "pipelines.operate"
    # The product-owner sign-off is recorded by a CA account (DDR-106); includes reading recipes to sign.
    RECIPES_PRODUCT_OWNER_SIGNOFF = "recipes.signoff.product_owner"


P = Permission
_KITCHEN_SHARED = frozenset(
    {
        P.KITCHEN_ORDERS_VIEW,
        P.KITCHEN_ORDERS_PROCESS,
        P.KITCHEN_RECIPES_VIEW,
        P.KITCHEN_LOW_STOCK_VIEW,
        P.KITCHEN_UNAVAILABILITY_REQUEST,
        P.KITCHEN_REVIEW_VIEW,
    }
)
_MGMT_SHARED = frozenset(
    {
        P.MGMT_OPERATIONS_VIEW,
        P.MGMT_STAFF_MANAGE,
        P.MGMT_AGENTS_ASSIGN,
        P.KITCHEN_MODE_CHANGE,
        P.MGMT_UNAVAILABILITY_APPROVE,
        P.MGMT_REFUND_EXCEPTIONAL,
        P.MGMT_REGIONAL_SETTINGS,
        P.MGMT_AUDIT_REGIONAL,
        P.MENU_PUBLISH,
        P.PIPELINES_VIEW,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CUSTOMER: frozenset(
        {
            P.CUSTOMER_PROFILE_READ,
            P.CUSTOMER_ORDERS_READ,
            P.CUSTOMER_ORDERS_PLACE,
            P.CUSTOMER_ORDERS_CANCEL,
            P.CUSTOMER_ADDRESSES_MANAGE,
        }
    ),
    Role.DELIVERY_AGENT: frozenset({P.DELIVERY_ASSIGNMENTS_VIEW}),
    Role.KITCHEN_STAFF: _KITCHEN_SHARED,
    Role.KITCHEN_MANAGER: _KITCHEN_SHARED
    | {
        P.KITCHEN_RECIPES_EDIT,
        P.KITCHEN_RECIPES_ACTIVATE,
        P.KITCHEN_INGREDIENTS_MANAGE,
        P.KITCHEN_STOCK_ADJUST,
        P.KITCHEN_MODE_CHANGE,
        P.KITCHEN_ETA_UPDATE,
        P.KITCHEN_RECIPES_WORKFLOW,
        P.KITCHEN_RECIPES_SIGNOFF,
        P.KITCHEN_REVIEW_ACKNOWLEDGE,
    },
    Role.REGIONAL_MANAGER: _MGMT_SHARED,
    Role.CENTRAL_ADMIN: _MGMT_SHARED
    | {
        P.MGMT_RM_MANAGE,
        P.MGMT_REFUND_OVERRIDE,
        P.MGMT_GLOBAL_SETTINGS,
        P.MGMT_AUDIT_GLOBAL,
        P.PIPELINES_OPERATE,
        P.RECIPES_PRODUCT_OWNER_SIGNOFF,
    },
}


@dataclass(frozen=True)
class Grant:
    role: Role
    region_id: uuid.UUID | None = None
    kitchen_id: uuid.UUID | None = None


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    grants: tuple[Grant, ...]
    session_id: uuid.UUID | None = None

    @property
    def roles(self) -> frozenset[Role]:
        return frozenset(g.role for g in self.grants)

    def permissions(self) -> frozenset[Permission]:
        return frozenset(p for g in self.grants for p in ROLE_PERMISSIONS[g.role])

    def portals(self) -> list[Portal]:
        return [portal for portal, roles in PORTAL_ROLES.items() if roles & self.roles]


def _grant_covers(
    principal: Principal,
    grant: Grant,
    *,
    customer_id: uuid.UUID | None,
    kitchen_id: uuid.UUID | None,
    region_id: uuid.UUID | None,
) -> bool:
    match grant.role:
        case Role.CENTRAL_ADMIN:
            return True
        case Role.CUSTOMER:
            return customer_id is not None and customer_id == principal.user_id
        case Role.KITCHEN_STAFF | Role.KITCHEN_MANAGER:
            return kitchen_id is not None and kitchen_id == grant.kitchen_id
        case Role.REGIONAL_MANAGER | Role.DELIVERY_AGENT:
            # Kitchen-scoped resources must pass their kitchen's region; per-assignment checks for
            # agents are added with delivery assignments (Task 9).
            return region_id is not None and region_id == grant.region_id


def can(
    principal: Principal,
    permission: Permission,
    *,
    customer_id: uuid.UUID | None = None,
    kitchen_id: uuid.UUID | None = None,
    region_id: uuid.UUID | None = None,
) -> bool:
    """True only if some grant includes the permission and its scope covers the resource."""
    return any(
        permission in ROLE_PERMISSIONS[grant.role]
        and _grant_covers(
            principal, grant, customer_id=customer_id, kitchen_id=kitchen_id, region_id=region_id
        )
        for grant in principal.grants
    )
