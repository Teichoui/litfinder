"""Validation tests for the Kavita auth branch of on_save_security."""

from __future__ import annotations

import shelfmark.config.security_handlers as handlers


def _set(monkeypatch, **values):
    """Make on_save_security see *values* as the effective merged config."""
    monkeypatch.setattr(handlers, "_load_effective_security_values", lambda v: dict(values))


def test_kavita_blocked_when_kavita_not_configured(monkeypatch):
    _set(monkeypatch, AUTH_METHOD="kavita")
    monkeypatch.setattr(handlers, "_has_kavita_config", lambda: False)
    monkeypatch.setattr(handlers, "_has_local_password_admin", lambda: True)

    result = handlers.on_save_security({"AUTH_METHOD": "kavita"})

    assert result["error"] is True
    assert "Kavita is not configured" in result["message"]


def test_kavita_blocked_without_local_admin(monkeypatch):
    _set(monkeypatch, AUTH_METHOD="kavita")
    monkeypatch.setattr(handlers, "_has_kavita_config", lambda: True)
    monkeypatch.setattr(handlers, "_has_local_password_admin", lambda: False)

    result = handlers.on_save_security({"AUTH_METHOD": "kavita"})

    assert result["error"] is True
    assert "local admin account" in result["message"]


def test_kavita_blocked_when_provisioning_on_but_abs_unreachable(monkeypatch):
    _set(monkeypatch, AUTH_METHOD="kavita", KAVITA_PROVISION_ABS_USERS=True)
    monkeypatch.setattr(handlers, "_has_kavita_config", lambda: True)
    monkeypatch.setattr(handlers, "_has_local_password_admin", lambda: True)
    monkeypatch.setattr(handlers, "_has_abs_config", lambda: True)
    monkeypatch.setattr(handlers, "_abs_reachable", lambda: False)

    result = handlers.on_save_security({"AUTH_METHOD": "kavita"})

    assert result["error"] is True
    assert "Audiobookshelf" in result["message"]


def test_kavita_ok_when_configured_with_admin_and_provisioning_off(monkeypatch):
    _set(monkeypatch, AUTH_METHOD="kavita", KAVITA_PROVISION_ABS_USERS=False)
    monkeypatch.setattr(handlers, "_has_kavita_config", lambda: True)
    monkeypatch.setattr(handlers, "_has_local_password_admin", lambda: True)

    result = handlers.on_save_security({"AUTH_METHOD": "kavita"})

    assert result["error"] is False
