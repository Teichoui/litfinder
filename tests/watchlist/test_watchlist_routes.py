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
