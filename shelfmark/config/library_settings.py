"""Library Folders settings tab.

A universal, server-agnostic registry of library folders. These folders are the
only locations the Files manager may touch, and they double as download
destinations. Any library server's folders can be listed here (Calibre,
Calibre-Web, Audiobookshelf, etc.) — add them manually, or import them from a
configured integration.
"""

from __future__ import annotations

from typing import Any

from shelfmark.core.config import config as app_config
from shelfmark.core.logger import setup_logger
from shelfmark.core.settings_registry import (
    ActionButton,
    HeadingField,
    SettingsField,
    TableField,
    register_settings,
    save_config_file,
)

logger = setup_logger(__name__)


def _import_abs_libraries(current_values: dict[str, Any]) -> dict[str, Any]:
    """Import Audiobookshelf libraries as folders, reusing the ABS connection.

    Uses the Audiobookshelf URL and API key configured on the Audiobookshelf
    settings tab (under Integrations), so there is only one place to enter
    those credentials. New libraries are merged in; existing rows are kept.
    """
    from shelfmark.integrations.audiobookshelf.client import AbsError, abs_list_libraries
    from shelfmark.integrations.audiobookshelf.sync import build_abs_config

    cfg = build_abs_config()
    if not cfg.base_url or not cfg.api_key:
        return {
            "success": False,
            "message": (
                "Audiobookshelf isn't connected yet. Open the Audiobookshelf tab "
                "(under Integrations), enter your URL and API key, test the connection, "
                "then come back here and import."
            ),
        }

    try:
        libraries = abs_list_libraries(cfg)
    except AbsError as exc:
        return {"success": False, "message": f"Couldn't reach Audiobookshelf: {exc}"}

    imported: list[dict[str, str]] = []
    for lib in libraries:
        name = str(lib.get("name") or "").strip()
        folders = lib.get("folders")
        path = ""
        if isinstance(folders, list) and folders and isinstance(folders[0], dict):
            path = str(folders[0].get("fullPath") or "").strip()
        if name and path:
            imported.append({"name": name, "path": path})

    if not imported:
        return {
            "success": False,
            "message": "No Audiobookshelf libraries with a folder path were found.",
        }

    existing = app_config.get("LIBRARY_FOLDERS") or []
    merged: list[dict[str, Any]] = [f for f in existing if isinstance(f, dict)]
    seen = {
        (str(f.get("name", "")).strip(), str(f.get("path", "")).strip()) for f in merged
    }

    added = 0
    for folder in imported:
        key = (folder["name"], folder["path"])
        if key not in seen:
            seen.add(key)
            merged.append(folder)
            added += 1

    save_config_file("library_folders", {"LIBRARY_FOLDERS": merged})
    app_config.refresh(force=True)

    details = [f"{f['name']} -> {f['path']}" for f in imported]
    if added == 0:
        return {
            "success": True,
            "message": "Your Audiobookshelf libraries are already listed — nothing new to add.",
            "details": details,
        }
    return {
        "success": True,
        "message": (
            f"Imported {added} librar{'y' if added == 1 else 'ies'} — reload the page to see them."
        ),
        "details": details,
    }


@register_settings("library_folders", "Library Folders", icon="folder", order=14)
def library_folders_settings() -> list[SettingsField]:
    """Universal library-folder registry used by the Files manager and downloads."""
    return [
        HeadingField(
            key="library_folders_heading",
            title="Library Folders",
            description=(
                "Define the folders that make up your libraries. The Files manager "
                "can browse and organize files inside these folders, and they appear "
                "as destinations when you download. Works with any library server."
            ),
        ),
        ActionButton(
            key="import_abs_libraries",
            label="Import Libraries from Audiobookshelf",
            description=(
                "Fetches your libraries from the Audiobookshelf connection set up on the "
                "Audiobookshelf tab and adds them to the table below."
            ),
            style="primary",
            callback=_import_abs_libraries,
        ),
        TableField(
            key="LIBRARY_FOLDERS",
            label="Libraries",
            description="Add as many libraries as you want.",
            columns=[
                {
                    "key": "name",
                    "label": "Library Name",
                    "type": "text",
                    "placeholder": "e.g. Audiobooks",
                },
                {
                    "key": "path",
                    "label": "Path",
                    "type": "text",
                    "placeholder": "e.g. /mnt/audiobooks",
                },
            ],
            add_label="Add Library",
            empty_message="No libraries configured. Add one manually, or import from Audiobookshelf above.",
            default=[],
        ),
    ]
