"""Tests for abs_iter_inventory's audio-track filtering.

ABS libraries are typed "book" regardless of whether they hold audiobook or
ebook-only content, so an item with no audio tracks must not be reported as an
owned audiobook just because it lives in a "book" library.
"""

from __future__ import annotations

from shelfmark.integrations.audiobookshelf import client as client_mod
from shelfmark.integrations.audiobookshelf.client import AbsConfig, abs_iter_inventory

_CFG = AbsConfig(base_url="http://abs:13378", api_key="key")


def _item(title: str, author: str, num_tracks: int | None) -> dict:
    media: dict = {"metadata": {"title": title, "authorName": author}}
    if num_tracks is not None:
        media["numTracks"] = num_tracks
    return {"media": media}


def test_iter_inventory_skips_items_with_no_audio_tracks(monkeypatch):
    monkeypatch.setattr(client_mod, "abs_list_libraries", lambda _cfg: [{"id": 1, "name": "Books"}])
    monkeypatch.setattr(
        client_mod,
        "_iter_library_items",
        lambda _cfg, _lib_id: iter(
            [
                _item("Devil's Bride", "Stephanie Laurens", num_tracks=12),
                _item("A Rake's Vow", "Stephanie Laurens", num_tracks=0),
                _item("Scandal's Bride", "Stephanie Laurens", num_tracks=None),
            ]
        ),
    )

    results = list(abs_iter_inventory(_CFG, []))

    assert [r["title"] for r in results] == ["Devil's Bride"]


def test_iter_inventory_falls_back_to_num_audio_files(monkeypatch):
    monkeypatch.setattr(
        client_mod, "abs_list_libraries", lambda _cfg: [{"id": 1, "name": "Audiobooks"}]
    )

    def _item_with_audio_files(title: str, num_audio_files: int) -> dict:
        return {
            "media": {
                "metadata": {"title": title, "authorName": "Author"},
                "numAudioFiles": num_audio_files,
            }
        }

    monkeypatch.setattr(
        client_mod,
        "_iter_library_items",
        lambda _cfg, _lib_id: iter([_item_with_audio_files("On a Wild Night", 8)]),
    )

    results = list(abs_iter_inventory(_CFG, []))

    assert [r["title"] for r in results] == ["On a Wild Night"]


def test_iter_inventory_honors_explicit_zero_num_tracks(monkeypatch):
    """An explicit numTracks: 0 must not fall back to numAudioFiles — ABS reporting
    zero playable tracks is a real signal, not a missing-field placeholder."""
    monkeypatch.setattr(
        client_mod, "abs_list_libraries", lambda _cfg: [{"id": 1, "name": "Audiobooks"}]
    )
    monkeypatch.setattr(
        client_mod,
        "_iter_library_items",
        lambda _cfg, _lib_id: iter(
            [
                {
                    "media": {
                        "metadata": {"title": "Corrupt Item", "authorName": "Author"},
                        "numTracks": 0,
                        "numAudioFiles": 5,
                    }
                }
            ]
        ),
    )

    results = list(abs_iter_inventory(_CFG, []))

    assert results == []
