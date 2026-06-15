"""Destination planning helpers for post-processing outputs."""

from __future__ import annotations

import uuid
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from shelfmark.core.logger import setup_logger
from shelfmark.core.utils import (
    get_destination,
)
from shelfmark.core.utils import (
    is_audiobook as check_audiobook,
)
from shelfmark.download.fs import run_blocking_io
from shelfmark.download.permissions_debug import log_path_permission_context
from shelfmark.release_sources import SourceUnavailableError, get_source

if TYPE_CHECKING:
    from collections.abc import Callable

    from shelfmark.core.models import DownloadTask

logger = setup_logger("shelfmark.download.postprocess.pipeline")


def validate_destination(
    destination: Path, status_callback: Callable[[str, str | None], None]
) -> bool:
    """Validate destination path is absolute, exists, and writable."""
    if not destination.is_absolute():
        logger.warning("Destination must be absolute: %s", destination)
        status_callback("error", f"Destination must be absolute: {destination}")
        return False

    destination_exists = run_blocking_io(destination.exists)
    if destination_exists and not run_blocking_io(destination.is_dir):
        logger.warning("Destination is not a directory: %s", destination)
        status_callback("error", f"Destination is not a directory: {destination}")
        return False

    created_by_us = False
    if not destination_exists:
        try:
            run_blocking_io(destination.mkdir, parents=True, exist_ok=True)
            created_by_us = True
        except (OSError, PermissionError) as exc:
            log_path_permission_context("destination_create", destination)
            logger.warning("Cannot create destination: %s (%s)", destination, exc)
            status_callback("error", f"Cannot create destination: {destination} ({exc})")
            return False

    test_path = destination / f".shelfmark_write_test_{uuid.uuid4().hex}.tmp"

    try:
        test_content = (
            f"This file was created to verify if '{destination}' is writable. "
            "It should've been automatically deleted. Feel free to delete it.\n"
        )
        run_blocking_io(test_path.write_text, test_content)
        run_blocking_io(test_path.unlink, missing_ok=True)
    except OSError as exc:
        logger.debug("Destination write probe path: %s", test_path)
        log_path_permission_context("destination_write_probe", destination)
        logger.warning("Destination not writable: %s (%s)", destination, exc)
        status_callback("error", f"Destination not writable: {destination} ({exc})")
        if created_by_us:
            with suppress(OSError):
                run_blocking_io(destination.rmdir)
        return False

    return True


def get_final_destination(task: DownloadTask) -> Path:
    """Get final destination directory, with content-type routing support."""
    # An explicit per-download destination (chosen in the download picker) wins
    # over both source overrides and content-type routing.  Re-validate it
    # against the current allowed-destinations list so that:
    # (a) a stale retry payload pointing to a now-removed folder falls back
    #     gracefully rather than writing outside allowed roots, and
    # (b) the containment invariant is upheld independently of how
    #     destination_override was set.
    if task.destination_override:
        from shelfmark.core.utils import get_named_download_destinations

        candidate = Path(task.destination_override)
        allowed = {
            Path(d["path"])
            for d in get_named_download_destinations(
                user_id=task.user_id, username=task.username
            )
        }
        if any(
            candidate == allowed_path
            or str(candidate).startswith(str(allowed_path).rstrip("/") + "/")
            for allowed_path in allowed
        ):
            return candidate
        logger.warning(
            "destination_override '%s' is not within any current allowed destination; "
            "falling back to automatic content-type routing",
            candidate,
        )

    is_audiobook = check_audiobook(task.content_type)

    try:
        override = get_source(task.source).get_destination_override(task)
    except (ValueError, SourceUnavailableError):
        override = None

    if override:
        return override

    return get_destination(
        is_audiobook=is_audiobook,
        user_id=task.user_id,
        username=task.username,
    )
