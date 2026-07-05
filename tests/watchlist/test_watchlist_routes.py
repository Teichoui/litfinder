"""Tests for watchlist API route validation."""

from typing import Any

import pytest
from flask import Flask

from shelfmark.watchlist.routes import init_watchlist_routes, watchlist_bp


class RejectingWatchlistDB:
    """Fake DB that fails if validation lets invalid author names through."""

    def add_author(self, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("add_author should not be called")

    def get_author(self, watch_id: int) -> dict[str, Any]:
        return {"id": watch_id, "user_id": 1}

    def update_author(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("update_author should not be called")


class RecordingWatchlistDB:
    def __init__(self) -> None:
        self.user_ids: list[int] = []

    def list_authors(self, user_id: int, **_kwargs: Any) -> list[dict[str, Any]]:
        self.user_ids.append(user_id)
        return [{"id": 10, "user_id": user_id, "author_name": "No Auth Author"}]


class FakeReleaseWatchlistDB:
    """Fake DB backing the release-action endpoint tests."""

    def __init__(self, releases: dict[int, dict[str, Any]]) -> None:
        self._releases = releases
        self.updated: list[tuple[int, str]] = []

    def get_release(self, release_id: int) -> dict[str, Any] | None:
        return self._releases.get(release_id)

    def update_release_action(
        self, release_id: int, *, action_status: str, request_id: int | None = None
    ) -> dict[str, Any] | None:
        self.updated.append((release_id, action_status))
        release = self._releases.get(release_id)
        if release is None:
            return None
        release = {**release, "action_status": action_status}
        self._releases[release_id] = release
        return release


class FakeUserDB:
    def __init__(self) -> None:
        self.users_by_username: dict[str, dict[str, Any]] = {}
        self.created_count = 0

    def get_user(self, *, username: str | None = None, **_kwargs: Any) -> dict[str, Any] | None:
        if username is None:
            return None
        return self.users_by_username.get(username)

    def create_user(self, **kwargs: Any) -> dict[str, Any]:
        self.created_count += 1
        username = kwargs["username"]
        user = {
            "id": self.created_count,
            "username": username,
            "display_name": kwargs.get("display_name"),
            "role": kwargs.get("role", "user"),
        }
        self.users_by_username[username] = user
        return user


@pytest.fixture
def app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.secret_key = "test"
    flask_app.register_blueprint(watchlist_bp)
    init_watchlist_routes(RejectingWatchlistDB())  # pyright: ignore[reportArgumentType]
    return flask_app


@pytest.fixture
def authed_client(app: Flask):
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["db_user_id"] = 1
        yield client


def test_add_author_rejects_non_string_author_name(authed_client):
    response = authed_client.post(
        "/api/watchlist/authors",
        json={"author_name": 123, "hardcover_author_id": "hc-1"},
    )

    assert response.status_code == 400
    assert response.json == {"error": "author_name must be a string"}


def test_update_author_rejects_non_string_author_name(authed_client):
    response = authed_client.patch("/api/watchlist/authors/1", json={"author_name": 123})

    assert response.status_code == 400
    assert response.json == {"error": "author_name must be a string"}


def test_no_auth_mode_uses_stable_watchlist_owner():
    flask_app = Flask(__name__)
    flask_app.secret_key = "test"
    flask_app.register_blueprint(watchlist_bp)
    watchlist_db = RecordingWatchlistDB()
    user_db = FakeUserDB()
    init_watchlist_routes(  # pyright: ignore[reportArgumentType]
        watchlist_db,
        user_db=user_db,
        resolve_auth_mode=lambda: "none",
    )

    with flask_app.test_client() as client:
        first = client.get("/api/watchlist/authors")
        second = client.get("/api/watchlist/authors")

    assert first.status_code == 200
    assert second.status_code == 200
    assert watchlist_db.user_ids == [1, 1]
    assert user_db.created_count == 1


def test_auth_mode_still_requires_session():
    flask_app = Flask(__name__)
    flask_app.secret_key = "test"
    flask_app.register_blueprint(watchlist_bp)
    init_watchlist_routes(  # pyright: ignore[reportArgumentType]
        RecordingWatchlistDB(),
        user_db=FakeUserDB(),
        resolve_auth_mode=lambda: "builtin",
    )

    with flask_app.test_client() as client:
        response = client.get("/api/watchlist/authors")

    assert response.status_code == 401
    assert response.json == {"error": "Not authenticated"}


def _release_app(releases: dict[int, dict[str, Any]]) -> tuple[Flask, FakeReleaseWatchlistDB]:
    flask_app = Flask(__name__)
    flask_app.secret_key = "test"
    flask_app.register_blueprint(watchlist_bp)
    watchlist_db = FakeReleaseWatchlistDB(releases)
    init_watchlist_routes(watchlist_db)  # pyright: ignore[reportArgumentType]
    return flask_app, watchlist_db


def test_update_release_action_succeeds_for_owner():
    flask_app, watchlist_db = _release_app(
        {5: {"id": 5, "user_id": 1, "action_status": "detected"}}
    )

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["db_user_id"] = 1
        response = client.patch("/api/watchlist/releases/5", json={"action_status": "skipped"})

    assert response.status_code == 200
    assert response.json["action_status"] == "skipped"
    assert watchlist_db.updated == [(5, "skipped")]


def test_update_release_action_rejects_other_users_release():
    flask_app, watchlist_db = _release_app(
        {5: {"id": 5, "user_id": 2, "action_status": "detected"}}
    )

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["db_user_id"] = 1
        response = client.patch("/api/watchlist/releases/5", json={"action_status": "skipped"})

    assert response.status_code == 403
    assert response.json == {"error": "Forbidden"}
    assert watchlist_db.updated == []


def test_update_release_action_404s_for_missing_release():
    flask_app, _ = _release_app({})

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["db_user_id"] = 1
        response = client.patch("/api/watchlist/releases/999", json={"action_status": "skipped"})

    assert response.status_code == 404
    assert response.json == {"error": "Release not found"}


def test_update_release_action_rejects_invalid_status():
    flask_app, watchlist_db = _release_app(
        {5: {"id": 5, "user_id": 1, "action_status": "detected"}}
    )

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["db_user_id"] = 1
        response = client.patch("/api/watchlist/releases/5", json={"action_status": "bogus"})

    assert response.status_code == 400
    assert response.json == {"error": "Invalid action_status"}
    assert watchlist_db.updated == []


@pytest.mark.parametrize("action_status", ["queued", "detected"])
def test_update_release_action_rejects_non_user_actions(action_status):
    """queued/detected aren't valid direct user actions on this endpoint — queued
    belongs to whatever eventually creates the download request, and detected is
    the initial state, not something to transition back into."""
    flask_app, watchlist_db = _release_app(
        {5: {"id": 5, "user_id": 1, "action_status": "detected"}}
    )

    with flask_app.test_client() as client:
        with client.session_transaction() as session:
            session["db_user_id"] = 1
        response = client.patch("/api/watchlist/releases/5", json={"action_status": action_status})

    assert response.status_code == 400
    assert response.json == {"error": "Invalid action_status"}
    assert watchlist_db.updated == []


def test_update_release_action_requires_authentication():
    flask_app, _ = _release_app({5: {"id": 5, "user_id": 1, "action_status": "detected"}})

    with flask_app.test_client() as client:
        response = client.patch("/api/watchlist/releases/5", json={"action_status": "skipped"})

    assert response.status_code == 401
    assert response.json == {"error": "Not authenticated"}
