"""Reuse the identity world and the management team (test users, second region, cleanup)."""

from app.modules.identity.tests.test_auth_integration import world  # noqa: F401 - pytest fixture
from app.modules.management.tests.test_management_integration import team  # noqa: F401 - pytest fixture
