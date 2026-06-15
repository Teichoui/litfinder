"""Library Folders settings tab.

A universal, server-agnostic registry of library folders. These folders are the
only locations the Files manager may touch, and they double as download
destinations. Any library server's folders can be listed here (Calibre,
Calibre-Web, Audiobookshelf, etc.) — add them manually, or import them from a
configured integration.
"""

from __future__ import annotations

from shelfmark.core.logger import setup_logger
from shelfmark.core.settings_registry import (
    HeadingField,
    SettingsField,
    TableField,
    register_settings,
)

logger = setup_logger(__name__)


@register_settings("library_folders", "Library Folders", icon="folder", order=22)
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
            empty_message="No libraries configured. Add one manually here.",
            default=[],
        ),
    ]
