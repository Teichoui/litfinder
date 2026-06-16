"""Calibre library reader: pull ebook inventory from a Calibre ``metadata.db``.

Calibre, Calibre-Web and Calibre-Web-Automated all share the same on-disk
library database (``metadata.db``), a plain SQLite file. This module opens it
read-only and yields normalized book records so Shelfmark can flag ebooks the
user already owns. It never writes to the Calibre database.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = setup_logger(__name__)

CALIBRE_DISPLAY_NAME = "Calibre-Web / CWA"
_DB_FILENAME = "metadata.db"
_CONNECT_TIMEOUT = 30

# One row per book: first author, first series + index, and ISBN (if any).
# LEFT JOINs keep books that have no author, series, or ISBN; GROUP BY collapses
# the extra author/identifier rows, keeping the first match per book.
_INVENTORY_SQL = """
SELECT
    b.id            AS id,
    b.title         AS title,
    b.series_index  AS series_index,
    a.name          AS author,
    s.name          AS series_name,
    i.val           AS isbn
FROM books b
LEFT JOIN books_authors_link bal ON bal.book = b.id
LEFT JOIN authors a ON a.id = bal.author
LEFT JOIN books_series_link bsl ON bsl.book = b.id
LEFT JOIN series s ON s.id = bsl.series
LEFT JOIN identifiers i ON i.book = b.id AND i.type = 'isbn'
GROUP BY b.id
"""


class CalibreError(Exception):
    """Raised when reading the Calibre library database fails."""


@dataclass(frozen=True)
class CalibreConfig:
    """Connection settings for the Calibre-Web / CWA integration."""

    db_path: str


def resolve_db_path(raw_path: str) -> Path | None:
    """Resolve a user-entered path to the Calibre ``metadata.db`` file.

    Accepts either the database file itself or the library folder that contains
    it. Returns None when nothing usable is found.
    """
    text = (raw_path or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_dir():
        path = path / _DB_FILENAME
    if path.is_file():
        return path
    return None


def _connect(cfg: CalibreConfig) -> sqlite3.Connection:
    """Open the Calibre database read-only, raising CalibreError on failure."""
    db_path = resolve_db_path(cfg.db_path)
    if db_path is None:
        msg = f"{CALIBRE_DISPLAY_NAME} library database not found"
        raise CalibreError(msg)
    try:
        # mode=ro: never write to the user's library; respects writer locks via
        # the busy timeout so a momentary Calibre-Web write doesn't fail the read.
        uri = f"{db_path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=_CONNECT_TIMEOUT)
    except sqlite3.Error as exc:
        msg = f"Could not open {CALIBRE_DISPLAY_NAME} database: {exc}"
        raise CalibreError(msg) from exc
    conn.row_factory = sqlite3.Row
    return conn


def _parse_isbn(raw: object) -> tuple[str | None, str | None]:
    """Split a raw ISBN string into (isbn_13, isbn_10); either may be None."""
    text = str(raw or "").replace("-", "").strip()
    if len(text) == 13 and text.isdigit():
        return text, None
    if len(text) == 10 and text[:9].isdigit() and (text[9].isdigit() or text[9].upper() == "X"):
        return None, text.upper()
    return None, None


def calibre_book_count(cfg: CalibreConfig) -> int:
    """Return the number of books in the Calibre library (for the test action)."""
    conn = _connect(cfg)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM books")
        return int(cur.fetchone()[0])
    except sqlite3.Error as exc:
        msg = f"Failed to read {CALIBRE_DISPLAY_NAME} library: {exc}"
        raise CalibreError(msg) from exc
    finally:
        conn.close()


def calibre_iter_inventory(cfg: CalibreConfig) -> Iterator[dict[str, Any]]:
    """Yield normalized ebook records from the Calibre library database."""
    conn = _connect(cfg)
    try:
        try:
            cursor = conn.execute(_INVENTORY_SQL)
        except sqlite3.Error as exc:
            msg = f"Failed to query {CALIBRE_DISPLAY_NAME} library: {exc}"
            raise CalibreError(msg) from exc

        for row in cursor:
            title = str(row["title"] or "").strip()
            if not title:
                continue
            series_name = str(row["series_name"] or "").strip() or None
            # Calibre stores series_index even for standalone books (default 1.0);
            # only treat it as a volume number when the book is actually in a series.
            series_index: float | None = None
            if series_name is not None and row["series_index"] is not None:
                try:
                    series_index = float(row["series_index"])
                except TypeError, ValueError:
                    series_index = None
            isbn_13, isbn_10 = _parse_isbn(row["isbn"])
            yield {
                "kind": "book",
                "library_id": None,
                "series_id": None,
                "series_name": series_name,
                "title": title,
                "author": str(row["author"] or "").strip(),
                "isbn_13": isbn_13,
                "isbn_10": isbn_10,
                "series_index": series_index,
            }
    finally:
        conn.close()
