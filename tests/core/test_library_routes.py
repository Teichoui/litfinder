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


def test_organize_accepts_source_from_download_destination(tmp_path: Path, monkeypatch) -> None:
    """A completed download outside library roots can still be sent to a library."""
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    downloaded_file = downloads_dir / "book.epub"
    downloaded_file.write_text("content")

    app = Flask(__name__)
    app.secret_key = "test-secret"
    register_library_routes(app, resolve_auth_mode=lambda: "none")
    monkeypatch.setattr(
        "shelfmark.core.utils.get_library_folders",
        lambda: [{"name": "Books", "path": str(library_dir)}],
    )
    monkeypatch.setattr(
        "shelfmark.core.config.config.get",
        lambda key, default=None, **kwargs: str(downloads_dir)
        if key == "DESTINATION"
        else default,
    )

    client = app.test_client()
    response = client.post(
        "/api/library/organize",
        json={"files": [{"path": str(downloaded_file)}], "target_folder": str(library_dir)},
    )

    assert response.status_code == 200
    assert response.json["success"] is True
    assert response.json["moved_files"] == [
        {"original_path": str(downloaded_file), "new_path": str(library_dir / "book.epub")}
    ]
    assert (library_dir / "book.epub").exists()
    assert not downloaded_file.exists()


def test_organize_rejects_source_outside_all_roots(tmp_path: Path, monkeypatch) -> None:
    """Sources outside both library folders and download destinations stay rejected."""
    library_dir = tmp_path / "library"
    library_dir.mkdir()
    stray_file = tmp_path / "stray" / "book.epub"
    stray_file.parent.mkdir()
    stray_file.write_text("content")

    app = Flask(__name__)
    app.secret_key = "test-secret"
    register_library_routes(app, resolve_auth_mode=lambda: "none")
    monkeypatch.setattr(
        "shelfmark.core.utils.get_library_folders",
        lambda: [{"name": "Books", "path": str(library_dir)}],
    )
    monkeypatch.setattr(
        "shelfmark.core.config.config.get",
        lambda key, default=None, **kwargs: default,
    )

    client = app.test_client()
    response = client.post(
        "/api/library/organize",
        json={"files": [{"path": str(stray_file)}], "target_folder": str(library_dir)},
    )

    assert response.status_code == 200
    assert response.json["success"] is False
    assert response.json["failed_files"][0]["path"] == str(stray_file)
    assert stray_file.exists()
