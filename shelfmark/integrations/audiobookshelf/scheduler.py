"""APScheduler-based scheduling for the Audiobookshelf inventory sync.

One process-wide BackgroundScheduler holds a cron job (configurable) plus
on-demand debounced jobs triggered when a download completes.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from shelfmark.core.config import config
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import coerce_bool
from shelfmark.integrations.audiobookshelf.sync import run_abs_sync

logger = setup_logger(__name__)

DEFAULT_CRON = "0 * * * *"
_CRON_JOB_ID = "abs_sync_cron"
_DOWNLOAD_JOB_ID = "abs_sync_after_download"
_DOWNLOAD_DEBOUNCE_SECONDS = 60

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def validate_cron(expression: str) -> CronTrigger:
    """Parse a 5-field cron expression, raising ValueError on failure."""
    return CronTrigger.from_crontab(expression.strip(), timezone=UTC)


def _ensure_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        scheduler = BackgroundScheduler(timezone=UTC)
        scheduler.start()
        _scheduler = scheduler
        logger.info("Audiobookshelf scheduler started")
    return _scheduler


def _apply_cron(scheduler: BackgroundScheduler, *, enabled: bool, expression: str) -> None:
    """Add/replace or remove the cron job for the given enabled/expression."""
    existing = scheduler.get_job(_CRON_JOB_ID)
    if not enabled:
        if existing is not None:
            scheduler.remove_job(_CRON_JOB_ID)
            logger.info("Audiobookshelf cron sync disabled; job removed")
        return

    expression = (expression or DEFAULT_CRON).strip()
    try:
        trigger = validate_cron(expression)
    except (ValueError, TypeError):
        logger.warning(
            "Invalid Audiobookshelf cron '%s'; falling back to '%s'", expression, DEFAULT_CRON
        )
        trigger = validate_cron(DEFAULT_CRON)

    scheduler.add_job(
        run_abs_sync,
        trigger=trigger,
        id=_CRON_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    logger.info("Audiobookshelf cron sync scheduled: '%s'", expression)


def start_scheduler() -> None:
    """Start the scheduler and apply the configured cron job. Idempotent."""
    with _lock:
        scheduler = _ensure_scheduler()
        _apply_cron(
            scheduler,
            enabled=coerce_bool(config.get("ABS_SYNC_ENABLED", False)),
            expression=str(config.get("ABS_SYNC_CRON", DEFAULT_CRON) or DEFAULT_CRON),
        )


def reschedule(*, enabled: bool, expression: str) -> None:
    """Update the cron job with explicit values (called from settings on_save).

    Explicit values avoid a race with the config-refresh that happens after the
    on-save handler returns.
    """
    with _lock:
        scheduler = _ensure_scheduler()
        _apply_cron(scheduler, enabled=enabled, expression=expression)


def request_sync_after_download() -> None:
    """Schedule a single debounced sync shortly after a download completes.

    Repeated calls within the debounce window coalesce into one run, giving
    Audiobookshelf time to ingest the new file before we re-scan. When
    ABS_SCAN_ON_DOWNLOAD is enabled, the run first triggers an ABS folder scan
    and waits for it to settle — needed when ABS sits on a network share and only
    detects new files on its own timer.
    """
    if not coerce_bool(config.get("ABS_SYNC_ON_DOWNLOAD", False)):
        return
    scan_first = coerce_bool(config.get("ABS_SCAN_ON_DOWNLOAD", False))
    with _lock:
        scheduler = _ensure_scheduler()
        run_date = datetime.now(UTC) + timedelta(seconds=_DOWNLOAD_DEBOUNCE_SECONDS)
        scheduler.add_job(
            run_abs_sync,
            trigger="date",
            run_date=run_date,
            id=_DOWNLOAD_JOB_ID,
            kwargs={"scan_first": scan_first},
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    logger.debug("Audiobookshelf post-download sync scheduled in %ds", _DOWNLOAD_DEBOUNCE_SECONDS)
