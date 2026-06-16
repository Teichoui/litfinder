"""Audiobookshelf library sync: pull audiobook inventory into the local snapshot.

Single-flight: concurrent triggers (cron + on-download + manual) coalesce so
only one sync runs at a time.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

from shelfmark.core.audiobookshelf_inventory_service import get_abs_inventory_service
from shelfmark.core.config import config
from shelfmark.core.logger import setup_logger
from shelfmark.integrations.audiobookshelf.client import (
    AbsConfig,
    AbsError,
    abs_iter_inventory,
    abs_library_item_count,
    abs_list_libraries,
    abs_scan_library,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = setup_logger(__name__)

_sync_lock = threading.Lock()

# Bound the wait for ABS to finish scanning so a stuck scan never hangs the sync.
_SCAN_POLL_INTERVAL_SECONDS = 5
_SCAN_POLL_TIMEOUT_SECONDS = 120


def _notify_new_audiobooks(new_books: list[dict[str, Any]]) -> None:
    """Fire an "Available in Library" admin notification per newly-found audiobook."""
    if not new_books:
        return
    try:
        from shelfmark.core.notifications import (
            NotificationContext,
            NotificationEvent,
            notify_admin,
        )
    except ImportError:
        logger.debug("Notifications unavailable; skipping audiobook-available alerts")
        return

    for book in new_books:
        try:
            context = NotificationContext(
                event=NotificationEvent.LIBRARY_AVAILABLE,
                title=str(book.get("title") or book.get("series_name") or "Unknown title"),
                author=str(book.get("author") or "Unknown author"),
                content_type="audiobook",
            )
            notify_admin(NotificationEvent.LIBRARY_AVAILABLE, context)
        except (RuntimeError, TypeError, ValueError) as exc:
            logger.warning("Failed to send audiobook-available notification: %s", exc)


def _cfg_value(overrides: Mapping[str, Any] | None, key: str, default: Any = "") -> Any:
    if overrides is not None:
        value = overrides.get(key)
        if value not in (None, ""):
            return value
    return config.get(key, default)


def build_abs_config(overrides: Mapping[str, Any] | None = None) -> AbsConfig:
    """Build an AbsConfig from saved config, optionally overridden by form values."""
    base_url = str(_cfg_value(overrides, "ABS_URL", "") or "").strip().rstrip("/")
    api_key = str(_cfg_value(overrides, "ABS_API_KEY", "") or "").strip()
    return AbsConfig(base_url=base_url, api_key=api_key, verify_tls=True)


def _selected_library_ids(overrides: Mapping[str, Any] | None) -> list[str]:
    raw = _cfg_value(overrides, "ABS_SYNC_LIBRARY_IDS", []) or []
    if isinstance(raw, list):
        return [str(value).strip() for value in raw if str(value).strip()]
    return []


def _resolve_scan_library_ids(cfg: AbsConfig, library_ids: list[Any]) -> list[Any]:
    """Return the library IDs to scan: the configured subset, or all book libraries."""
    if library_ids:
        return list(library_ids)
    return [lib["id"] for lib in abs_list_libraries(cfg) if lib.get("id") is not None]


def trigger_abs_scan_and_wait(cfg: AbsConfig, library_ids: list[Any]) -> None:
    """Trigger an ABS folder scan for the given libraries and wait for it to settle.

    ABS's scan endpoint is fire-and-forget (returns 200 immediately, scans in the
    background) and exposes no completion status over REST. To order the later
    inventory read after the scan, we record each library's item count, trigger
    the scan, then poll until the count stops changing (new item ingested) or a
    timeout elapses. Best-effort: any ABS error is logged and the sync proceeds
    with whatever ABS currently reports.
    """
    try:
        targets = _resolve_scan_library_ids(cfg, library_ids)
    except AbsError as exc:
        logger.warning("Audiobookshelf scan skipped (could not list libraries): %s", exc)
        return

    before: dict[Any, int] = {}
    for library_id in targets:
        try:
            before[library_id] = abs_library_item_count(cfg, library_id)
            abs_scan_library(cfg, library_id)
        except AbsError as exc:
            logger.warning("Audiobookshelf scan trigger failed for library %s: %s", library_id, exc)

    if not before:
        return

    deadline = time.monotonic() + _SCAN_POLL_TIMEOUT_SECONDS
    pending = set(before)
    while pending and time.monotonic() < deadline:
        time.sleep(_SCAN_POLL_INTERVAL_SECONDS)
        for library_id in list(pending):
            try:
                if abs_library_item_count(cfg, library_id) != before[library_id]:
                    pending.discard(library_id)
            except AbsError:
                # Transient read failure: stop waiting on this library, let the
                # inventory read below report whatever ABS has.
                pending.discard(library_id)

    if pending:
        logger.info(
            "Audiobookshelf scan wait timed out after %ds; syncing current state",
            _SCAN_POLL_TIMEOUT_SECONDS,
        )


def run_abs_sync(
    overrides: Mapping[str, Any] | None = None, *, scan_first: bool = False
) -> dict[str, Any]:
    """Run a full Audiobookshelf inventory sync. Returns a summary dict.

    When *scan_first* is set, trigger an ABS folder scan and wait for it to
    settle before reading the inventory — used by the post-download path so the
    just-added book is ingested by ABS (which, on network shares, only scans on
    its own timer) before Shelfmark reads it.

    On error returns ``{"success": False, "error": "..."}`` without raising.
    """
    inventory = get_abs_inventory_service()
    if inventory is None:
        return {"success": False, "error": "Inventory store unavailable"}

    cfg = build_abs_config(overrides)
    if not cfg.base_url or not cfg.api_key:
        return {"success": False, "error": "Audiobookshelf URL and API key are required"}

    if not _sync_lock.acquire(blocking=False):
        logger.info("Audiobookshelf sync already running; skipping overlapping trigger")
        return {"success": False, "error": "Sync already in progress"}

    try:
        library_ids: list[Any] = list(_selected_library_ids(overrides))
        if scan_first:
            trigger_abs_scan_and_wait(cfg, library_ids)
        records = list(abs_iter_inventory(cfg, library_ids))
        result = inventory.replace_inventory(records)
        # Count distinct library IDs seen in the records rather than making a
        # second abs_list_libraries() call (which would mask a successful sync
        # as a failure if ABS is momentarily unavailable after the write).
        if library_ids:
            libraries = len(library_ids)
        else:
            seen_lib_ids: set[Any] = {r.get("library_id") for r in records if r.get("library_id")}
            libraries = len(seen_lib_ids)
        books = len(records)
        new_books = result.get("new_books") or []
        logger.info(
            "Audiobookshelf sync complete: %d libraries, %d audiobooks (%d rows, %d new)",
            libraries,
            books,
            result.get("rows", 0),
            len(new_books),
        )
        _notify_new_audiobooks(new_books)
        return {
            "success": True,
            "libraries": libraries,
            "books": books,
            "new_books": len(new_books),
        }
    except AbsError as exc:
        logger.warning("Audiobookshelf sync failed: %s", exc)
        return {"success": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("Unexpected error during Audiobookshelf sync")
        return {"success": False, "error": str(exc)}
    finally:
        _sync_lock.release()
