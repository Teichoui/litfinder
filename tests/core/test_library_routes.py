from __future__ import annotations

from pathlib import Path

from flask import Flask

from shelfmark.core.library_routes import register_library_routes


def test_library_routes_require_admin_when_auth_enabled(tmp_path: Path, monkeypatch) -> None:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    register_library_routes(app, resolve_auth_mode=lambda: "builtin")
    monkeypatch.setattr(
        "shelfmark.core.utils.get_library_folders",
        lambda: [{"name": "Books", "path": str(tmp_path)}],
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = "reader"
        sess["is_admin"] = False

    response = client.get("/api/library-folders")

    assert response.status_code == 403
    assert response.json == {"action": "browse", "error": "Admin required"}


def test_library_routes_allow_admin_when_auth_enabled(tmp_path: Path, monkeypatch) -> None:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    register_library_routes(app, resolve_auth_mode=lambda: "builtin")
    monkeypatch.setattr(
        "shelfmark.core.utils.get_library_folders",
        lambda: [{"name": "Books", "path": str(tmp_path)}],
    )

    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = "admin"
        sess["is_admin"] = True

    response = client.get("/api/library-folders")

    assert response.status_code == 200
    assert response.json == [{"name": "Books", "path": str(tmp_path)}]
