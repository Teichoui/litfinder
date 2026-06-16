"""Tests for the Kavita login auth-mode resolution and active-user policy."""

from __future__ import annotations

from shelfmark.core.auth_modes import (
    AUTH_SOURCE_KAVITA,
    determine_auth_mode,
    is_user_active_for_auth_mode,
)

_KAVITA_CONFIG = {"AUTH_METHOD": "kavita", "KAVITA_URL": "http://kavita:5000"}


def test_kavita_mode_active_with_url_and_local_admin() -> None:
    """Kavita mode resolves only when a URL is set and a local admin exists."""
    mode = determine_auth_mode(_KAVITA_CONFIG, None, has_local_admin=True)
    assert mode == AUTH_SOURCE_KAVITA


def test_kavita_mode_falls_back_without_local_admin() -> None:
    """Without a local admin fallback, Kavita mode is refused (avoids lockout)."""
    mode = determine_auth_mode(_KAVITA_CONFIG, None, has_local_admin=False)
    assert mode == "none"


def test_kavita_mode_falls_back_without_url() -> None:
    """A selected-but-unconfigured Kavita mode falls back to none."""
    mode = determine_auth_mode(
        {"AUTH_METHOD": "kavita", "KAVITA_URL": ""}, None, has_local_admin=True
    )
    assert mode == "none"


def test_disable_local_auth_satisfies_admin_requirement() -> None:
    """DISABLE_LOCAL_AUTH counts as the local-admin prerequisite being met."""
    mode = determine_auth_mode(_KAVITA_CONFIG, None, has_local_admin=False, disable_local_auth=True)
    assert mode == AUTH_SOURCE_KAVITA


def test_local_user_active_under_kavita_mode() -> None:
    """A local (builtin) user stays active under Kavita mode for the fallback."""
    local_user = {"auth_source": "builtin"}
    assert is_user_active_for_auth_mode(local_user, AUTH_SOURCE_KAVITA) is True


def test_kavita_user_active_only_under_kavita_mode() -> None:
    """A Kavita-sourced user is active under Kavita mode but not under builtin."""
    kavita_user = {"auth_source": "kavita"}
    assert is_user_active_for_auth_mode(kavita_user, AUTH_SOURCE_KAVITA) is True
    assert is_user_active_for_auth_mode(kavita_user, "builtin") is False
