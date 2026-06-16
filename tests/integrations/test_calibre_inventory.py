"""Tests for the Calibre-Web / CWA ownership integration.

Builds a throwaway Calibre ``metadata.db`` with the standard schema, then checks
that the reader yields normalized records and that the inventory snapshot
matches owned books (by ISBN, title+author, and series) while leaving unowned
books alone.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from shelfmark.core.calibre_inventory_service import CalibreInventoryService
from shelfmark.integrations.calibre.client import (
    CalibreConfig,
    calibre_book_count,
    calibre_iter_inventory,
    resolve_db_path,
)

# Minimal subset of the Calibre library schema that the reader queries.
_SCHEMA = """
CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, series_index REAL DEFAULT 1.0);
CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE books_authors_link (id INTEGER PRIMARY KEY, book INTEGER, author INTEGER);
CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE books_series_link (id INTEGER PRIMARY KEY, book INTEGER, series INTEGER);
CREATE TABLE identifiers (id INTEGER PRIMARY KEY, book INTEGER, type TEXT, val TEXT);
"""


def _build_calibre_db(path: Path) -> None:
    """Create a Calibre metadata.db with three representative books."""
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    # 1: standalone book with an ISBN-13.
    # 2 & 3: two volumes of a series, with authors but no ISBN.
    conn.executemany(
        "INSERT INTO books (id, title, series_index) VALUES (?, ?, ?)",
        [
            (1, "The Standalone", 1.0),
            (2, "The Final Empire", 1.0),
            (3, "The Well of Ascension", 2.0),
        ],
    )
    conn.executemany(
        "INSERT INTO authors (id, name) VALUES (?, ?)",
        [
            (1, "Jane Writer"),
            (2, "Brandon Sanderson"),
        ],
    )
    conn.executemany(
        "INSERT INTO books_authors_link (book, author) VALUES (?, ?)",
        [
            (1, 1),
            (2, 2),
            (3, 2),
        ],
    )
    conn.execute("INSERT INTO series (id, name) VALUES (1, 'Mistborn')")
    conn.executemany(
        "INSERT INTO books_series_link (book, series) VALUES (?, ?)",
        [
            (2, 1),
            (3, 1),
        ],
    )
    conn.execute("INSERT INTO identifiers (book, type, val) VALUES (1, 'isbn', '9780000000001')")
    conn.commit()
    conn.close()


def test_reader_yields_normalized_records(tmp_path: Path) -> None:
    """The reader normalizes ISBN, author, and series fields per book."""
    db = tmp_path / "metadata.db"
    _build_calibre_db(db)
    cfg = CalibreConfig(db_path=str(db))

    assert calibre_book_count(cfg) == 3
    records = {rec["title"]: rec for rec in calibre_iter_inventory(cfg)}

    standalone = records["The Standalone"]
    assert standalone["isbn_13"] == "9780000000001"
    assert standalone["series_name"] is None
    # Calibre's default series_index of 1.0 must not be treated as a volume number
    # for a standalone book.
    assert standalone["series_index"] is None

    volume = records["The Final Empire"]
    assert volume["author"] == "Brandon Sanderson"
    assert volume["series_name"] == "Mistborn"
    assert volume["series_index"] == 1.0


def test_resolve_db_path_accepts_file_or_folder(tmp_path: Path) -> None:
    """A folder path resolves to its metadata.db; a missing path resolves to None."""
    db = tmp_path / "metadata.db"
    _build_calibre_db(db)
    assert resolve_db_path(str(tmp_path)) == db  # folder -> metadata.db
    assert resolve_db_path(str(db)) == db  # file -> itself
    assert resolve_db_path(str(tmp_path / "nope")) is None


def test_inventory_lookup_matches_owned_books(tmp_path: Path) -> None:
    """After a sync, owned books match (ISBN / title+author / series); others don't."""
    db = tmp_path / "metadata.db"
    _build_calibre_db(db)
    cfg = CalibreConfig(db_path=str(db))

    users_db = tmp_path / "users.db"
    service = CalibreInventoryService(str(users_db))
    service.initialize()
    result = service.replace_inventory(calibre_iter_inventory(cfg))

    assert result["rows"] == 3
    assert service.count() == 3

    # Owned by ISBN.
    assert service.lookup_book(isbn_13="978-0-00-000000-1") is True
    # Owned by title + author.
    assert service.lookup_book(title="The Final Empire", author="Brandon Sanderson")
    # Owned by series name + volume index.
    assert service.lookup_book(series_name="Mistborn", series_index=2) is True
    # Series coverage counts both owned volumes.
    assert service.series_coverage("Mistborn") == 2

    # Not owned.
    assert service.lookup_book(title="A Book We Do Not Have", author="Nobody") is False
    assert service.lookup_book(isbn_13="9781111111111") is False
