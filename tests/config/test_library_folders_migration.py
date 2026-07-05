"""Tests for consolidating library folders into the dedicated tab."""

import json
from pathlib import Path


def _seed(plugins: Path, tab: str, values: dict) -> None:
    (plugins / f"{tab}.json").write_text(json.dumps(values))


def _setup_config_dir(monkeypatch, tmp_path: Path) -> Path:
    import shelfmark.config.env as env
    import shelfmark.core.settings_registry as registry

    config_dir = tmp_path / "config"
    plugins = config_dir / "plugins"
    plugins.mkdir(parents=True)
    monkeypatch.setattr(env, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(registry, "_get_config_dir", lambda: config_dir)
    return plugins


def test_migrate_library_folders_consolidates_and_prunes(monkeypatch, tmp_path):
    import shelfmark.core.settings_registry as registry

    plugins = _setup_config_dir(monkeypatch, tmp_path)
    _seed(
        plugins,
        "download_sources",
        {
            "DIRECT_DOWNLOAD_ENABLED": True,
            "LIBRARY_FOLDERS": [
                {"name": "Audiobooks", "path": "/mnt/abs"},
                {"name": "Books", "path": "/mnt/books"},
            ],
            "AUDIOBOOKSHELF_URL": "http://abs:13378",
            "AUDIOBOOKSHELF_API_KEY": "legacy-key",
        },
    )
    _seed(
        plugins,
        "downloads",
        {
            "LIBRARY_FOLDERS": [
                {"name": "Audiobooks", "path": "/mnt/abs"},
                {"name": "Comics", "path": "/mnt/c"},
            ]
        },
    )
    _seed(plugins, "library_folders", {"LIBRARY_FOLDERS": [{"name": "Manual", "path": "/mnt/m"}]})

    registry.migrate_library_folders()

    folders = registry.load_config_file("library_folders")["LIBRARY_FOLDERS"]
    # Manual entry preserved, legacy entries appended, duplicate "Audiobooks" deduped.
    assert folders == [
        {"name": "Manual", "path": "/mnt/m"},
        {"name": "Audiobooks", "path": "/mnt/abs"},
        {"name": "Books", "path": "/mnt/books"},
        {"name": "Comics", "path": "/mnt/c"},
    ]

    # Legacy copies are pruned, unrelated keys left intact.
    download_sources = registry.load_config_file("download_sources")
    assert "LIBRARY_FOLDERS" not in download_sources
    assert "AUDIOBOOKSHELF_URL" not in download_sources
    assert "AUDIOBOOKSHELF_API_KEY" not in download_sources
    assert download_sources["DIRECT_DOWNLOAD_ENABLED"] is True
    assert "LIBRARY_FOLDERS" not in registry.load_config_file("downloads")

    # Old import credentials fold into the main Audiobookshelf connection.
    abs_config = registry.load_config_file("audiobookshelf")
    assert abs_config["ABS_URL"] == "http://abs:13378"
    assert abs_config["ABS_API_KEY"] == "legacy-key"


def test_migrate_library_folders_keeps_existing_abs_connection(monkeypatch, tmp_path):
    import shelfmark.core.settings_registry as registry

    plugins = _setup_config_dir(monkeypatch, tmp_path)
    _seed(
        plugins,
        "download_sources",
        {"AUDIOBOOKSHELF_URL": "http://old", "AUDIOBOOKSHELF_API_KEY": "old"},
    )
    _seed(plugins, "audiobookshelf", {"ABS_URL": "http://new", "ABS_API_KEY": "new"})

    registry.migrate_library_folders()

    abs_config = registry.load_config_file("audiobookshelf")
    assert abs_config["ABS_URL"] == "http://new"
    assert abs_config["ABS_API_KEY"] == "new"


def test_migrate_library_folders_is_idempotent(monkeypatch, tmp_path):
    import shelfmark.core.settings_registry as registry

    plugins = _setup_config_dir(monkeypatch, tmp_path)
    _seed(plugins, "download_sources", {"LIBRARY_FOLDERS": [{"name": "A", "path": "/a"}]})

    registry.migrate_library_folders()
    first = registry.load_config_file("library_folders")["LIBRARY_FOLDERS"]
    registry.migrate_library_folders()
    second = registry.load_config_file("library_folders")["LIBRARY_FOLDERS"]

    assert first == second == [{"name": "A", "path": "/a"}]


def test_library_folders_is_the_only_canonical_tab():
    import shelfmark.config.library_settings
    import shelfmark.config.settings  # noqa: F401
    from shelfmark.core.settings_registry import get_settings_field_map, get_settings_tab

    field_map = get_settings_field_map()
    assert "LIBRARY_FOLDERS" in field_map
    assert field_map["LIBRARY_FOLDERS"][1] == "library_folders"

    # The Download Sources tab no longer carries a Library Folders section.
    download_sources = get_settings_tab("download_sources")
    keys = {field.key for field in download_sources.fields if hasattr(field, "key")}
    assert "LIBRARY_FOLDERS" not in keys
    assert "AUDIOBOOKSHELF_URL" not in keys
