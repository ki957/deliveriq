"""Reuse the identity integration world (test users, a second region and kitchen, cleanup)."""

from app.modules.identity.tests.test_auth_integration import world  # noqa: F401 - pytest fixture
