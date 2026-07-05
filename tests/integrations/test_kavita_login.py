"""Tests for Kavita SSO login, ABS auto-provisioning, and auth-mode resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from shelfmark.core.auth_modes import determine_auth_mode
from shelfmark.integrations.kavita.client import KavitaError, kavita_login_user


class _FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.exceptions.HTTPError(f"status {self.status_code}")


class TestKavitaLoginUser:
    def test_returns_identity_on_success(self, monkeypatch):
        captured: dict[str, object] = {}

        def fake_request(method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            return _FakeResponse(
                200,
                {
                    "token": "jwt-token",
                    "username": "Reader",
                    "email": "reader@example.com",
                    "roles": ["User", "Admin"],
                    "apiKey": "abc",
                },
            )

        monkeypatch.setattr("shelfmark.integrations.kavita.client.requests.request", fake_request)

        result = kavita_login_user("https://kavita.example.net/", "reader", "pw")

        assert captured["method"] == "POST"
        assert captured["url"] == "https://kavita.example.net/api/Account/login"
        assert captured["json"] == {"username": "reader", "password": "pw"}
        assert result["token"] == "jwt-token"
        assert result["username"] == "Reader"
        assert result["email"] == "reader@example.com"
        assert result["is_admin"] is True

    def test_non_admin_roles_are_not_admin(self, monkeypatch):
        monkeypatch.setattr(
            "shelfmark.integrations.kavita.client.requests.request",
            lambda *a, **k: _FakeResponse(200, {"token": "t", "username": "u", "roles": ["User"]}),
        )
        result = kavita_login_user("https://kavita.example.net", "u", "pw")
        assert result["is_admin"] is False

    def test_bad_credentials_raise(self, monkeypatch):
        monkeypatch.setattr(
            "shelfmark.integrations.kavita.client.requests.request",
            lambda *a, **k: _FakeResponse(401, {}),
        )
        with pytest.raises(KavitaError, match="Invalid Kavita username or password"):
            kavita_login_user("https://kavita.example.net", "u", "bad")

    def test_missing_url_raises(self):
        with pytest.raises(KavitaError, match="URL is required"):
            kavita_login_user("", "u", "pw")

    def test_missing_token_raises(self, monkeypatch):
        monkeypatch.setattr(
            "shelfmark.integrations.kavita.client.requests.request",
            lambda *a, **k: _FakeResponse(200, {"username": "u"}),
        )
        with pytest.raises(KavitaError, match="did not return a token"):
            kavita_login_user("https://kavita.example.net", "u", "pw")


class TestDetermineAuthModeKavita:
    def _config(self, **overrides):
        cfg = {"AUTH_METHOD": "kavita", "KAVITA_URL": "https://kavita.example.net"}
        cfg.update(overrides)
        return cfg

    def test_kavita_active_with_url_and_local_admin(self):
        assert determine_auth_mode(self._config(), cwa_db_path=None) == "kavita"

    def test_kavita_falls_back_to_none_without_url(self):
        assert determine_auth_mode(self._config(KAVITA_URL=""), cwa_db_path=None) == "none"

    def test_kavita_falls_back_to_none_without_local_admin(self):
        assert (
            determine_auth_mode(self._config(), cwa_db_path=None, has_local_admin=False) == "none"
        )

    def test_disable_local_auth_keeps_kavita_without_admin(self):
        assert (
            determine_auth_mode(
                self._config(),
                cwa_db_path=None,
                has_local_admin=False,
                disable_local_auth=True,
            )
            == "kavita"
        )


class TestProvisionAbsUser:
    def _patch_config(self, monkeypatch, *, enabled: bool):
        import shelfmark.integrations.audiobookshelf.provisioning as prov

        monkeypatch.setattr(
            prov.config,
            "get",
            lambda key, default=None: enabled if key == "KAVITA_PROVISION_ABS_USERS" else default,
        )
        return prov

    def test_disabled_does_nothing(self, monkeypatch):
        prov = self._patch_config(monkeypatch, enabled=False)
        called = {"create": False}
        monkeypatch.setattr(
            prov, "build_abs_config", lambda: pytest.fail("must not build config when disabled")
        )
        prov.provision_abs_user("reader", "pw")
        assert called["create"] is False

    def test_creates_user_when_missing(self, monkeypatch):
        prov = self._patch_config(monkeypatch, enabled=True)
        created: list[tuple[str, str]] = []
        monkeypatch.setattr(
            prov, "build_abs_config", lambda: SimpleNamespace(base_url="u", api_key="k")
        )
        monkeypatch.setattr(prov, "abs_user_exists", lambda cfg, username: False)
        monkeypatch.setattr(
            prov,
            "abs_create_user",
            lambda cfg, username, password: created.append((username, password)),
        )
        prov.provision_abs_user("reader", "pw")
        assert created == [("reader", "pw")]

    def test_skips_creation_when_user_exists(self, monkeypatch):
        prov = self._patch_config(monkeypatch, enabled=True)
        monkeypatch.setattr(
            prov, "build_abs_config", lambda: SimpleNamespace(base_url="u", api_key="k")
        )
        monkeypatch.setattr(prov, "abs_user_exists", lambda cfg, username: True)
        monkeypatch.setattr(
            prov, "abs_create_user", lambda *a, **k: pytest.fail("should not create existing user")
        )
        prov.provision_abs_user("reader", "pw")

    def test_never_raises_on_failure(self, monkeypatch):
        prov = self._patch_config(monkeypatch, enabled=True)
        monkeypatch.setattr(
            prov,
            "build_abs_config",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        # Must swallow the error so login is never blocked.
        prov.provision_abs_user("reader", "pw")
