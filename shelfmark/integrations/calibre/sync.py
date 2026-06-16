"""Calibre-Web / CWA library sync: read the metadata.db into the local snapshot.

Single-flight: concurrent triggers (cron + on-download + manual) coalesce so
only one sync runs at a time.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from shelfmark.core.calibre_inventory_service import get_calibre_inventory_service
from shelfmark.core.config import config
from shelfmark.core.logger import setup_logger
from shelfmark.integrations.calibre.client import (
    CalibreConfig,
    CalibreError,
    calibre_iter_inventory,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = setup_logger(__name__)

_sync_lock = threading.Lock()


def _notify_new_library_books(new_books: list[dict[str, Any]]) -> None:
    """Fire an "Available in Library" admin notification per newly-found book."""
    if not new_books:
        return
    try:
        from shelfmark.core.notifications import (
            NotificationContext,
            NotificationEvent,
            notify_admin,
        )
    except ImportError:
        logger.debug("Notifications unavailable; skipping library-available alerts")
        return

    for book in new_books:
        try:
            context = NotificationContext(
                event=NotificationEvent.LIBRARY_AVAILABLE,
                title=str(book.get("title") or book.get("series_name") or "Unknown title"),
                author=str(book.get("author") or "Unknown author"),
            )
            notify_admin(NotificationEvent.LIBRARY_AVAILABLE, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Failed to send library-available notification: %s", exc)


def _cfg_value(overrides: Mapping[str, Any] | None, key: str, default: Any = "") -> Any:
    if overrides is not None:
        value = overrides.get(key)
        if value not in (None, ""):
            return value
    return config.get(key, default)


def build_calibre_config(overrides: Mapping[str, Any] | None = None) -> CalibreConfig:
    """Build a CalibreConfig from saved config, optionally overridden by form values."""
    db_path = str(_cfg_value(overrides, "CALIBRE_LIBRARY_PATH", "") or "").strip()
    return CalibreConfig(db_path=db_path)


def run_calibre_sync(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run a full Calibre inventory sync. Returns a summary dict.

    On error returns ``{"success": False, "error": "..."}`` without raising.
    """
    inventory = get_calibre_inventory_service()
    if inventory is None:
        return {"success": False, "error": "Inventory store unavailable"}

    cfg = build_calibre_config(overrides)
    if not cfg.db_path:
        return {"success": False, "error": "Calibre library path is required"}

    if not _sync_lock.acquire(blocking=False):
        logger.info("Calibre sync already running; skipping overlapping trigger")
        return {"success": False, "error": "Sync already in progress"}

    try:
        records = list(calibre_iter_inventory(cfg))
        result = inventory.replace_inventory(records)
        books = len(records)
        new_books = result.get("new_books") or []
        logger.info(
            "Calibre sync complete: %d books (%d rows, %d new)",
            books,
            result.get("rows", 0),
            len(new_books),
        )
        _notify_new_library_books(new_books)
        return {
            "success": True,
            "books": books,
            "new_books": len(new_books),
        }
    except CalibreError as exc:
        logger.warning("Calibre sync failed: %s", exc)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected error during Calibre sync")
        return {"success": False, "error": str(exc)}
    finally:
        _sync_lock.release()
