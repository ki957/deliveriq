"""Customer menu publication lifecycle and readiness checklist (DDR-11, DDR-31, DDR-48).

Standard library only. Mirrored in PostgreSQL (migrations 0002-0003).
"""

from __future__ import annotations

from enum import StrEnum

TEST_PREFIX = "TEST – "  # DDR-48: every synthetic dish name starts with this (en dash)


class Publication(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_PUBLICATION = "READY_FOR_PUBLICATION"
    PUBLISHED = "PUBLISHED"
    TEMPORARILY_UNAVAILABLE = "TEMPORARILY_UNAVAILABLE"
    RETIRED = "RETIRED"


M = Publication
MENU_INITIAL = frozenset({M.DRAFT})
MENU_TRANSITIONS = frozenset(
    {
        (M.DRAFT, M.READY_FOR_PUBLICATION),
        (M.READY_FOR_PUBLICATION, M.PUBLISHED),
        (M.PUBLISHED, M.TEMPORARILY_UNAVAILABLE),
        (M.TEMPORARILY_UNAVAILABLE, M.PUBLISHED),
        (M.PUBLISHED, M.RETIRED),
    }
)
PUBLISHING_ROLES = frozenset({"REGIONAL_MANAGER", "CENTRAL_ADMIN"})  # DDR-31


def can_transition(current: Publication, target: Publication) -> bool:
    return (current, target) in MENU_TRANSITIONS


def is_test_name(name: str) -> bool:
    return name.startswith(TEST_PREFIX)
