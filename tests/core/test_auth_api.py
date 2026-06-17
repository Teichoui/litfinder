"""Focused auth API regression tests for lockout handling."""

from __future__ import annotations

import importlib
from datetime import datetime
from unittest.mock import patch

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture(scope="module")
def main_module():
    """Import `shelfmark.main` with background startup disabled."""
    with patch("shelfmark.download.orchestrator.start"):
        import shelfmark.main as main

        importlib.reload(main)
        return main


@pytest.fixture
def client(main_module):
    main_module.failed_login_attempts.clear()
    try:
        yield main_module.app.test_client()
    finally:
        main_module.failed_login_attempts.clear()


@pytest.fixture
def temp_user_db(tmp_path):
    from shelfmark.core.user_db import UserDB

    db = UserDB(str(tmp_path / "users.db"))
    db.initialize()
    return db


class TestLoginSemantics:
    def test_login_rejects_missing_payload(self, main_module, client):
        response = client.post("/api/auth/login")

        assert response.status_code == 400
        assert response.get_json()["error"] == "No data provided"

    def test_login_in_none_mode_sets_session_without_db_user(self, main_module, client):
        with patch.object(main_module, "get_auth_mode", return_value="none"):
            response = client.post(
                "/api/auth/login",
                json={"username": "guest", "password": "ignored", "remember_me": True},
            )

        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        with client.session_transaction() as sess:
            assert sess["user_id"] == "guest"
            assert "db_user_id" not in sess
            assert sess.permanent is True

    def test_login_builtin_success_sets_session_and_admin_flag(
        self, main_module, client, temp_user_db, monkeypatch
    ):
        monkeypatch.setattr(main_module, "user_db", temp_user_db)
        user = temp_user_db.create_user(
            username="alice",
            password_hash=generate_password_hash("secret"),
            display_name="Alice Example",
            role="admin",
        )

        with patch.object(main_module, "get_auth_mode", return_value="builtin"):
            response = client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "secret", "remember_me": False},
            )

        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        with client.session_transaction() as sess:
            assert sess["user_id"] == "alice"
            assert sess["db_user_id"] == user["id"]
            assert sess["is_admin"] is True
            assert sess.permanent is False
        assert "alice" not in main_module.failed_login_attempts

    def test_login_builtin_rejects_wrong_password_and_tracks_failure(
        self, main_module, client, temp_user_db, monkeypatch
    ):
        monkeypatch.setattr(main_module, "user_db", temp_user_db)
        temp_user_db.create_user(
            username="alice",
            password_hash=generate_password_hash("secret"),
            role="user",
        )

        with patch.object(main_module, "get_auth_mode", return_value="builtin"):
            response = client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "wrong", "remember_me": False},
            )

        assert response.status_code == 401
        assert response.get_json()["error"] == "Invalid username or password."
        assert main_module.failed_login_attempts["alice"]["count"] == 1

    def test_login_rejects_proxy_mode(self, main_module, client):
        with patch.object(main_module, "get_auth_mode", return_value="proxy"):
            response = client.post(
                "/api/auth/login",
                json={"username": "alice", "password": "secret", "remember_me": False},
            )

        assert response.status_code == 401
        assert response.get_json()["error"] == "Proxy authentication is enabled"

    def test_login_rejects_oidc_when_local_auth_is_hidden(self, main_module, client):
        with patch.object(main_module, "get_auth_mode", return_value="oidc"):
            with patch.object(main_module, "HIDE_LOCAL_AUTH", True):
                response = client.post(
                    "/api/auth/login",
                    json={"username": "alice", "password": "secret", "remember_me": False},
                )

        assert response.status_code == 403
        assert response.get_json()["error"] == "Local authentication is disabled"

    @pytest.mark.parametrize("auth_mode", ["builtin", "oidc"])
    def test_login_rejects_password_auth_when_local_auth_is_disabled(
        self, main_module, client, auth_mode
    ):
        with patch.object(main_module, "get_auth_mode", return_value=auth_mode):
            with patch.object(main_module, "DISABLE_LOCAL_AUTH", True):
                response = client.post(
                    "/api/auth/login",
                    json={"username": "alice", "password": "wrong", "remember_me": False},
                )

        assert response.status_code == 403
        assert response.get_json()["error"] == "Local authentication is disabled"
        assert main_module.failed_login_attempts == {}

    def test_auth_check_none_mode_reports_full_access(self, main_module, client):
        with patch.object(main_module, "get_auth_mode", return_value="none"):
            response = client.get("/api/auth/check")

        assert response.status_code == 200
        assert response.get_json() == {
            "authenticated": True,
            "auth_required": False,
            "auth_mode": "none",
            "is_admin": True,
        }

    @pytest.mark.parametrize("auth_mode", ["builtin", "oidc"])
    def test_auth_check_hides_local_auth_when_disabled(self, main_module, client, auth_mode):
        with patch.object(main_module, "get_auth_mode", return_value=auth_mode):
            with patch.object(main_module, "DISABLE_LOCAL_AUTH", True):
                response = client.get("/api/auth/check")

        assert response.status_code == 200
        body = response.get_json()
        assert body["auth_mode"] == auth_mode
        assert body["auth_required"] is True
        assert body["authenticated"] is False
        assert body["hide_local_auth"] is True

    def test_auth_check_includes_display_name_for_authenticated_user(
        self, main_module, client, temp_user_db, monkeypatch
    ):
        monkeypatch.setattr(main_module, "user_db", temp_user_db)
        user = temp_user_db.create_user(
            username="alice",
            password_hash=generate_password_hash("secret"),
            display_name="Alice Example",
            role="admin",
        )

        with client.session_transaction() as sess:
            sess["user_id"] = "alice"
            sess["db_user_id"] = user["id"]
            sess["is_admin"] = True

        with patch.object(main_module, "get_auth_mode", return_value="builtin"):
            response = client.get("/api/auth/check")

        assert response.status_code == 200
        body = response.get_json()
        assert body["authenticated"] is True
        assert body["auth_required"] is True
        assert body["auth_mode"] == "builtin"
        assert body["is_admin"] is True
        assert body["username"] == "alice"
        assert body["display_name"] == "Alice Example"

    def test_logout_proxy_includes_logout_url_and_clears_session(self, main_module, client):
        with client.session_transaction() as sess:
            sess["user_id"] = "alice"
            sess["db_user_id"] = 1
            sess["is_admin"] = True

        with patch.object(main_module, "get_auth_mode", return_value="proxy"):
            with patch.object(
                main_module.app_config,
                "get",
                side_effect=lambda key, default=None, user_id=None: {
                    "PROXY_AUTH_LOGOUT_URL": "https://auth.example.com/logout",
                }.get(key, default),
            ):
                response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert response.get_json() == {
            "success": True,
            "logout_url": "https://auth.example.com/logout",
        }
        with client.session_transaction() as sess:
            assert "user_id" not in sess
            assert "db_user_id" not in sess
            assert "is_admin" not in sess


class TestKavitaLogin:
    def test_kavita_local_source_uses_db_password(
        self, main_module, client, temp_user_db, monkeypatch
    ):
        monkeypatch.setattr(main_module, "user_db", temp_user_db)
        user = temp_user_db.create_user(
            username="admin",
            password_hash=generate_password_hash("secret"),
            role="admin",
        )

        with patch.object(main_module, "get_auth_mode", return_value="kavita"):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "admin",
                    "password": "secret",
                    "remember_me": False,
                    "source": "local",
                },
            )

        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        with client.session_transaction() as sess:
            assert sess["user_id"] == "admin"
            assert sess["db_user_id"] == user["id"]
            assert sess["is_admin"] is True

    def test_kavita_source_validates_against_kavita_and_creates_session(
        self, main_module, client, temp_user_db, monkeypatch
    ):
        monkeypatch.setattr(main_module, "user_db", temp_user_db)
        monkeypatch.setattr(
            "shelfmark.integrations.kavita.client.kavita_login_user",
            lambda base_url, username, password: {
                "username": "reader",
                "email": "reader@example.com",
                "is_admin": False,
                "token": "t",
                "api_key": None,
            },
        )
        # Keep the provisioning hook inert so no ABS calls happen.
        monkeypatch.setattr(
            "shelfmark.integrations.audiobookshelf.provisioning.provision_abs_user",
            lambda username, password: None,
        )

        with patch.object(main_module, "get_auth_mode", return_value="kavita"):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "reader",
                    "password": "pw",
                    "remember_me": True,
                    "source": "kavita",
                },
            )

        assert response.status_code == 200
        assert response.get_json() == {"success": True}
        with client.session_transaction() as sess:
            assert sess["user_id"] == "reader"
            assert sess["is_admin"] is False
        created = temp_user_db.get_user(username="reader")
        assert created is not None
        assert created["auth_source"] == "kavita"

    def test_kavita_source_rejects_bad_credentials(
        self, main_module, client, temp_user_db, monkeypatch
    ):
        from shelfmark.integrations.kavita.client import KavitaError

        monkeypatch.setattr(main_module, "user_db", temp_user_db)

        def _raise(base_url, username, password):
            raise KavitaError("Invalid Kavita username or password")

        monkeypatch.setattr(
            "shelfmark.integrations.kavita.client.kavita_login_user", _raise
        )

        with patch.object(main_module, "get_auth_mode", return_value="kavita"):
            response = client.post(
                "/api/auth/login",
                json={
                    "username": "reader",
                    "password": "bad",
                    "remember_me": False,
                    "source": "kavita",
                },
            )

        assert response.status_code == 401
        assert response.get_json()["error"] == "Invalid username or password."
        assert main_module.failed_login_attempts["reader"]["count"] == 1

    def test_auth_check_advertises_kavita_login(self, main_module, client):
        overrides = {
            "KAVITA_DEFAULT_SOURCE": "local",
            "KAVITA_LOGIN_BUTTON_LABEL": "Sign in with Kavita",
        }
        with patch.object(main_module, "get_auth_mode", return_value="kavita"):
            with patch.object(
                main_module.app_config,
                "get",
                side_effect=lambda key, default=None, user_id=None: overrides.get(key, default),
            ):
                response = client.get("/api/auth/check")

        assert response.status_code == 200
        body = response.get_json()
        assert body["auth_mode"] == "kavita"
        assert body["kavita_login_enabled"] is True
        assert body["kavita_default_source"] == "local"
        assert body["kavita_button_label"] == "Sign in with Kavita"


class TestLoginLockoutRepair:
    def test_is_account_locked_repairs_missing_timestamp(self, main_module):
        main_module.failed_login_attempts.clear()
        main_module.failed_login_attempts["locked-user"] = {"count": main_module.MAX_LOGIN_ATTEMPTS}

        assert main_module.is_account_locked("locked-user") is True
        assert isinstance(
            main_module.failed_login_attempts["locked-user"].get("lockout_until"), datetime
        )

    def test_login_keeps_account_locked_when_timestamp_is_missing(self, main_module, client):
        main_module.failed_login_attempts["locked-user"] = {"count": main_module.MAX_LOGIN_ATTEMPTS}

        with patch.object(main_module, "get_auth_mode", return_value="builtin"):
            response = client.post(
                "/api/auth/login",
                json={"username": "locked-user", "password": "secret", "remember_me": False},
            )

        assert response.status_code == 429
        assert "Account temporarily locked" in response.get_json()["error"]
        assert isinstance(
            main_module.failed_login_attempts["locked-user"].get("lockout_until"), datetime
        )
