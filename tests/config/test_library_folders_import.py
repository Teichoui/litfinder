"""Tests for the Audiobookshelf -> Library Folders import action."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _FakeAbsConfig:
    base_url: str = "http://abs:13378"
    api_key: str = "key"


def _patch_abs(monkeypatch, libraries):
    import shelfmark.config.library_settings as mod

    monkeypatch.setattr(
        "shelfmark.integrations.audiobookshelf.sync.build_abs_config",
        lambda: _FakeAbsConfig(),
    )
    monkeypatch.setattr(
        "shelfmark.integrations.audiobookshelf.client.abs_list_libraries",
        lambda cfg: libraries,
    )
    monkeypatch.setattr(mod.app_config, "get", lambda key, default=None: [])
    monkeypatch.setattr(mod, "save_config_file", lambda tab, values: None)
    monkeypatch.setattr(mod.app_config, "refresh", lambda force=False: None)


def test_import_flags_paths_not_mounted_in_litfinder(monkeypatch, tmp_path):
    import shelfmark.config.library_settings as mod

    real_dir = tmp_path / "real"
    real_dir.mkdir()

    _patch_abs(
        monkeypatch,
        [
            {"name": "Audiobooks", "folders": [{"fullPath": str(real_dir)}]},
            {"name": "Ebooks", "folders": [{"fullPath": "/no/such/path"}]},
        ],
    )

    result = mod._import_abs_libraries({})

    assert result["success"] is True
    assert "1 of these folder path" in result["message"]
    assert any(d.startswith("✓ Audiobooks") for d in result["details"])
    assert any(
        d.startswith("⚠ Ebooks") and "not visible to LitFinder" in d for d in result["details"]
    )


def test_import_no_warning_when_all_paths_resolve(monkeypatch, tmp_path):
    import shelfmark.config.library_settings as mod

    real_dir = tmp_path / "real"
    real_dir.mkdir()

    _patch_abs(monkeypatch, [{"name": "Audiobooks", "folders": [{"fullPath": str(real_dir)}]}])

    result = mod._import_abs_libraries({})

    assert result["success"] is True
    assert "Heads up" not in result["message"]
    assert result["details"] == [f"✓ Audiobooks -> {real_dir}"]
