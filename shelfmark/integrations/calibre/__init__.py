"""Calibre-Web / CWA integration: ebook library ownership awareness.

Reads the Calibre ``metadata.db`` (the library database shared by Calibre,
Calibre-Web and Calibre-Web-Automated) so Shelfmark can flag ebooks already in
the library. Read-only: it never writes to the Calibre database.
"""
