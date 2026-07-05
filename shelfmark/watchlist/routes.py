"""Flask blueprint for Shelfmark watchlist API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Blueprint, jsonify, request

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from shelfmark.core.user_db import UserDB
    from shelfmark.watchlist.db import WatchlistDB

logger = setup_logger(__name__)

watchlist_bp = Blueprint("watchlist", __name__, url_prefix="/api/watchlist")
_VALID_WATCH_CONTENT_TYPES = {"ebook", "audiobook"}
_VALID_ACTION_STATUSES = {"detected", "queued", "skipped", "ignored"}
_NO_AUTH_WATCHLIST_USERNAME = "__no_auth_watchlist__"

# Populated by init_watchlist_routes()
_watchlist_db: WatchlistDB | None = None
_user_db: UserDB | None = None
_resolve_auth_mode: Callable[[], str] | None = None


def init_watchlist_routes(
    watchlist_db: WatchlistDB,
    *,
    user_db: UserDB | None = None,
    resolve_auth_mode: Callable[[], str] | None = None,
) -> None:
    """Bind the WatchlistDB instance used by route handlers."""
    global _resolve_auth_mode, _user_db, _watchlist_db
    _watchlist_db = watchlist_db
    _user_db = user_db
    _resolve_auth_mode = resolve_auth_mode


def _get_db() -> WatchlistDB:
    if _watchlist_db is None:
        msg = "WatchlistDB not initialized"
        raise RuntimeError(msg)
    return _watchlist_db


def _get_current_user_id() -> int | None:
    """Return the authenticated user's DB ID from the Flask session.

    Mirrors the pattern used in existing Shelfmark route handlers.
    """
    from flask import session

    raw = session.get("db_user_id")
    if raw is not None:
        try:
            return int(raw)
        except TypeError, ValueError:
            return None

    if _resolve_auth_mode is not None and _resolve_auth_mode() == "none":
        return _get_no_auth_user_id()

    return None


def _get_no_auth_user_id() -> int | None:
    if _user_db is None:
        return None

    user = _user_db.get_user(username=_NO_AUTH_WATCHLIST_USERNAME)
    if user is None:
        try:
            user = _user_db.create_user(
                username=_NO_AUTH_WATCHLIST_USERNAME,
                display_name="No-auth watchlist",
                role="user",
            )
        except ValueError:
            user = _user_db.get_user(username=_NO_AUTH_WATCHLIST_USERNAME)

    if user is None:
        return None
    try:
        return int(user["id"])
    except TypeError, ValueError, KeyError:
        return None


def _error(message: str, status: int = 400) -> Any:
    return jsonify({"error": message}), status


def _validate_watch_content_types(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return "watch_content_types must be an array"
    if not value:
        return "watch_content_types must not be empty"
    if any(v not in _VALID_WATCH_CONTENT_TYPES for v in value):
        return "watch_content_types must contain only ebook or audiobook"
    return None


# ------------------------------------------------------------------
# Author watch endpoints
# ------------------------------------------------------------------


@watchlist_bp.get("/authors")
def list_authors() -> Any:
    """GET /api/watchlist/authors — list watched authors for current user."""
    user_id = _get_current_user_id()
    if user_id is None:
        return _error("Not authenticated", 401)

    include_inactive = request.args.get("include_inactive", "false").lower() == "true"

    authors = _get_db().list_authors(user_id, include_inactive=include_inactive)
    return jsonify(authors)


@watchlist_bp.post("/authors")
def add_author() -> Any:
    """POST /api/watchlist/authors — add an author to the watchlist."""
    user_id = _get_current_user_id()
    if user_id is None:
        return _error("Not authenticated", 401)

    body = request.get_json(silent=True)
    if not body:
        return _error("Request body must be JSON")

    author_name = body.get("author_name", "")
    hardcover_author_id = body.get("hardcover_author_id") or None
    ol_author_key = body.get("ol_author_key") or None
    watch_content_types = body.get("watch_content_types")

    if not isinstance(author_name, str):
        return _error("author_name must be a string")
    if not author_name.strip():
        return _error("author_name is required")
    if hardcover_author_id is None and ol_author_key is None:
        return _error("At least one of hardcover_author_id or ol_author_key is required")

    if content_type_error := _validate_watch_content_types(watch_content_types):
        return _error(content_type_error)

    try:
        entry = _get_db().add_author(
            user_id=user_id,
            author_name=author_name,
            hardcover_author_id=hardcover_author_id,
            ol_author_key=ol_author_key,
            watch_content_types=watch_content_types,
        )
    except ValueError as e:
        logger.warning("Failed to add watchlist author: %s", e)
        if e.args[:1] == ("Watch entry already exists",):
            return _error("Watch entry already exists")
        return _error("Unable to add watch entry")

    return jsonify(entry), 201


@watchlist_bp.delete("/authors/<int:watch_id>")
def remove_author(watch_id: int) -> Any:
    """DELETE /api/watchlist/authors/<id> — remove an author from the watchlist."""
    user_id = _get_current_user_id()
    if user_id is None:
        return _error("Not authenticated", 401)

    entry = _get_db().get_author(watch_id)
    if entry is None:
        return _error("Watch entry not found", 404)
    if entry["user_id"] != user_id:
        return _error("Forbidden", 403)

    _get_db().remove_author(watch_id)
    return jsonify({"deleted": True, "id": watch_id})


@watchlist_bp.patch("/authors/<int:watch_id>")
def update_author(watch_id: int) -> Any:
    """PATCH /api/watchlist/authors/<id> — update is_active or watch_content_types."""
    user_id = _get_current_user_id()
    if user_id is None:
        return _error("Not authenticated", 401)

    entry = _get_db().get_author(watch_id)
    if entry is None:
        return _error("Watch entry not found", 404)
    if entry["user_id"] != user_id:
        return _error("Forbidden", 403)

    body = request.get_json(silent=True)
    if not body:
        return _error("Request body must be JSON")

    is_active = body.get("is_active")
    watch_content_types = body.get("watch_content_types")
    author_name = body.get("author_name")

    if is_active is not None and not isinstance(is_active, bool):
        return _error("is_active must be a boolean")
    if content_type_error := _validate_watch_content_types(watch_content_types):
        return _error(content_type_error)
    if author_name is not None and not isinstance(author_name, str):
        return _error("author_name must be a string")
    if author_name is not None and not author_name.strip():
        return _error("author_name must not be blank")

    try:
        updated = _get_db().update_author(
            watch_id,
            is_active=is_active,
            watch_content_types=watch_content_types,
            author_name=author_name,
        )
    except ValueError as e:
        logger.warning("Failed to update watchlist author %s: %s", watch_id, e)
        return _error("Unable to update watch entry")

    if updated is None:
        return _error("Watch entry not found", 404)

    return jsonify(updated)


# ------------------------------------------------------------------
# Release endpoints
# ------------------------------------------------------------------


@watchlist_bp.get("/releases")
def list_releases() -> Any:
    """GET /api/watchlist/releases — list detected releases for current user."""
    user_id = _get_current_user_id()
    if user_id is None:
        return _error("Not authenticated", 401)

    action_status = request.args.get("action_status") or None
    if action_status is not None and action_status not in _VALID_ACTION_STATUSES:
        return _error("Invalid action_status")

    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return _error("limit and offset must be integers")

    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    try:
        releases = _get_db().list_releases(
            user_id,
            action_status=action_status,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        logger.warning("Failed to list watchlist releases: %s", e)
        return _error("Unable to list watchlist releases")

    return jsonify(releases)


@watchlist_bp.patch("/releases/<int:release_id>")
def update_release(release_id: int) -> Any:
    """PATCH /api/watchlist/releases/<id> — mark a detected release queued/skipped/ignored."""
    user_id = _get_current_user_id()
    if user_id is None:
        return _error("Not authenticated", 401)

    entry = _get_db().get_release(release_id)
    if entry is None:
        return _error("Release not found", 404)
    if entry["user_id"] != user_id:
        return _error("Forbidden", 403)

    body = request.get_json(silent=True)
    if not body:
        return _error("Request body must be JSON")

    action_status = body.get("action_status")
    if action_status not in _VALID_ACTION_STATUSES:
        return _error("Invalid action_status")

    try:
        updated = _get_db().update_release_action(release_id, action_status=action_status)
    except ValueError as e:
        logger.warning("Failed to update watchlist release %s: %s", release_id, e)
        return _error("Unable to update release")

    if updated is None:
        return _error("Release not found", 404)

    return jsonify(updated)
