"""Tests for the Audiobookshelf scan-then-wait-then-sync ordering.

The post-download path can ask ABS to scan its folders before reading the
inventory (needed on network shares where ABS only scans on its own timer).
ABS's scan endpoint is fire-and-forget, so the code records each library's item
count, triggers the scan, then polls until the count changes or a timeout
elapses. These tests pin that ordering and the best-effort error handling.
"""

from __future__ import annotations

import shelfmark.integrations.audiobookshelf.sync as sync_mod
from shelfmark.integrations.audiobookshelf.client import AbsConfig, AbsError

_CFG = AbsConfig(base_url="http://abs:13378", api_key="key")


def _patch_no_wait(monkeypatch):
    """Make the poll loop instant: no real sleeping, deterministic clock."""
    ticks = iter(range(10_000))
    monkeypatch.setattr(sync_mod.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sync_mod.time, "monotonic", lambda: next(ticks))


def test_scan_waits_until_item_count_changes(monkeypatch):
    """It triggers a scan, then returns once the library's item count changes."""
    _patch_no_wait(monkeypatch)
    scanned: list[str] = []
    # Count is 5 before the scan, then 6 on the second poll (new item ingested).
    counts = iter([5, 5, 6])
    monkeypatch.setattr(sync_mod, "abs_library_item_count", lambda _cfg, _lib: next(counts))
    monkeypatch.setattr(sync_mod, "abs_scan_library", lambda _cfg, lib: scanned.append(lib))

    sync_mod.trigger_abs_scan_and_wait(_CFG, ["lib-1"])

    assert scanned == ["lib-1"]  # scan was triggered exactly once


def test_scan_times_out_when_count_never_changes(monkeypatch):
    """A scan that never adds an item gives up at the timeout instead of hanging."""
    monkeypatch.setattr(sync_mod.time, "sleep", lambda _seconds: None)
    # Clock jumps straight past the deadline after the first sleep.
    clock = iter([0.0, sync_mod._SCAN_POLL_TIMEOUT_SECONDS + 1])
    monkeypatch.setattr(sync_mod.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(sync_mod, "abs_library_item_count", lambda _cfg, _lib: 5)
    monkeypatch.setattr(sync_mod, "abs_scan_library", lambda _cfg, _lib: None)

    # Must return (not raise / not loop forever).
    sync_mod.trigger_abs_scan_and_wait(_CFG, ["lib-1"])


def test_scan_resolves_all_libraries_when_none_selected(monkeypatch):
    """With no library subset, it scans every book library ABS reports."""
    _patch_no_wait(monkeypatch)
    scanned: list[str] = []
    monkeypatch.setattr(
        sync_mod,
        "abs_list_libraries",
        lambda _cfg: [{"id": "a"}, {"id": "b"}],
    )
    monkeypatch.setattr(sync_mod, "abs_library_item_count", lambda _cfg, _lib: 0)
    monkeypatch.setattr(sync_mod, "abs_scan_library", lambda _cfg, lib: scanned.append(lib))

    sync_mod.trigger_abs_scan_and_wait(_CFG, [])

    assert sorted(scanned) == ["a", "b"]


def test_scan_trigger_error_is_swallowed(monkeypatch):
    """A failed scan trigger is logged, not raised — the sync still proceeds."""
    _patch_no_wait(monkeypatch)

    def _boom(_cfg, _lib):
        raise AbsError("scan requires an admin API key")

    monkeypatch.setattr(sync_mod, "abs_library_item_count", lambda _cfg, _lib: 0)
    monkeypatch.setattr(sync_mod, "abs_scan_library", _boom)

    # No exception escapes.
    sync_mod.trigger_abs_scan_and_wait(_CFG, ["lib-1"])


def test_scan_skipped_when_library_listing_fails(monkeypatch):
    """If ABS can't even list libraries, scanning is skipped (no crash)."""
    _patch_no_wait(monkeypatch)

    def _boom(_cfg):
        raise AbsError("Could not connect to Audiobookshelf")

    monkeypatch.setattr(sync_mod, "abs_list_libraries", _boom)

    sync_mod.trigger_abs_scan_and_wait(_CFG, [])  # empty subset -> needs listing
