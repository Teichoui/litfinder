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
