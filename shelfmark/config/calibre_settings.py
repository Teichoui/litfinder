"""Calibre-Web / CWA integration settings tab: library path and sync."""

from __future__ import annotations

from typing import Any

from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger
from shelfmark.core.request_helpers import coerce_bool
from shelfmark.core.settings_registry import (
    ActionButton,
    CheckboxField,
    HeadingField,
    SettingsField,
    TextField,
    register_on_save,
    register_settings,
)
from shelfmark.integrations.calibre.client import CalibreError, calibre_book_count
from shelfmark.integrations.calibre.scheduler import (
    DEFAULT_CRON,
    reschedule,
    validate_cron,
)
from shelfmark.integrations.calibre.sync import build_calibre_config, run_calibre_sync

logger = setup_logger(__name__)


def check_calibre_connection(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Test access to the Calibre library using current (possibly unsaved) values."""
    cfg = build_calibre_config(current_values or {})
    if not cfg.db_path:
        return {"success": False, "message": "Calibre library path is required"}
    try:
        count = calibre_book_count(cfg)
    except CalibreError as exc:
        return {"success": False, "message": str(exc)}
    return {
        "success": True,
        "message": f"Found Calibre library ({count} books)",
    }


def trigger_calibre_sync_now(current_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run an immediate Calibre sync using current form values."""
    result = run_calibre_sync(current_values or {})
    if not result.get("success"):
        return {"success": False, "message": result.get("error", "Sync failed")}
    return {
        "success": True,
        "message": f"Synced {result['books']} books from your Calibre library",
    }


@register_settings("calibre", "Calibre-Web / CWA", icon="library", order=8, group="integrations")
def calibre_settings() -> list[SettingsField]:
    """Calibre-Web / CWA library path and sync settings."""
    return [
        HeadingField(
            key="calibre_connection_heading",
            title="Library",
            description=(
                "Point Shelfmark at your Calibre library database so it can mark "
                "ebooks you already own. Calibre, Calibre-Web and Calibre-Web-"
                "Automated all share the same 'metadata.db' file."
            ),
        ),
        TextField(
            key="CALIBRE_LIBRARY_PATH",
            label="Library Path",
            description=(
                "Path (inside the Shelfmark container) to your Calibre 'metadata.db' "
                "file, or to the library folder that contains it. Mount your Calibre "
                "library as a read-only volume."
            ),
            placeholder="/calibre-library/metadata.db",
        ),
        ActionButton(
            key="test_calibre",
            label="Test Library",
            description="Verify Shelfmark can read the Calibre library database.",
            style="primary",
            callback=check_calibre_connection,
        ),
        HeadingField(
            key="calibre_sync_heading",
            title="Library Sync",
            description=(
                "Periodically read the Calibre library so Shelfmark can mark books "
                "and series you already own as available."
            ),
        ),
        CheckboxField(
            key="CALIBRE_SYNC_ENABLED",
            label="Enable Scheduled Sync",
            description="Run the Calibre library sync on the cron schedule below.",
            default=False,
        ),
        TextField(
            key="CALIBRE_SYNC_CRON",
            label="Sync Schedule (cron)",
            description="5-field cron expression. Default '0 * * * *' runs hourly.",
            placeholder=DEFAULT_CRON,
            default=DEFAULT_CRON,
        ),
        CheckboxField(
            key="CALIBRE_SYNC_ON_DOWNLOAD",
            label="Sync After Download Completes",
            description=(
                "In addition to the schedule, trigger a sync shortly after each "
                "download finishes (debounced)."
            ),
            default=False,
        ),
        ActionButton(
            key="calibre_sync_now",
            label="Sync Now",
            description="Read the full Calibre library immediately.",
            style="default",
            callback=trigger_calibre_sync_now,
        ),
    ]


def _on_save_calibre(values: dict[str, Any]) -> dict[str, Any]:
    """Validate the cron expression and apply the new schedule."""
    cron = values.get("CALIBRE_SYNC_CRON")
    if cron is not None and str(cron).strip():
        try:
            validate_cron(str(cron))
        except ValueError, TypeError:
            return {
                "error": True,
                "message": f"Invalid cron expression: {cron}",
            }

    enabled = values.get("CALIBRE_SYNC_ENABLED")
    if enabled is None:
        enabled = app_config.get("CALIBRE_SYNC_ENABLED", False)
    expression = values.get("CALIBRE_SYNC_CRON") or app_config.get(
        "CALIBRE_SYNC_CRON", DEFAULT_CRON
    )

    try:
        reschedule(enabled=coerce_bool(enabled), expression=str(expression or DEFAULT_CRON))
    except Exception:
        logger.exception("Failed to apply Calibre schedule after save")

    return {"error": False, "values": values}


register_on_save("calibre", _on_save_calibre)
