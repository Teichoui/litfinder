"""Audiobookshelf API integration for library browsing and management."""

from __future__ import annotations

import requests
from typing import Any

from shelfmark.core.config import config
from shelfmark.core.logger import setup_logger

logger = setup_logger(__name__)


class ABSError(Exception):
    pass


class ABSClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {api_key}"

    def _get(self, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.get(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            raise ABSError(f"ABS request failed: {exc}") from exc

    def _post(self, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as exc:
            raise ABSError(f"ABS request failed: {exc}") from exc

    def get_libraries(self) -> list[dict[str, Any]]:
        data = self._get("/api/libraries")
        return data.get("libraries", [])

    def get_library_items(self, library_id: str, limit: int = 50, page: int = 0) -> dict[str, Any]:
        params = {"limit": limit, "page": page, "sort": "media.title", "desc": 0}
        return self._get(f"/api/libraries/{library_id}/items", params=params)

    def scan_library(self, library_id: str) -> bool:
        try:
            self._post(f"/api/libraries/{library_id}/scan")
            return True
        except ABSError:
            logger.error("Failed to trigger scan for library %s", library_id)
            return False

    def find_library_for_path(self, path: str) -> dict[str, Any] | None:
        for library in self.get_libraries():
            for folder in library.get("folders", []):
                folder_path = folder.get("fullPath", "")
                if folder_path and (path.startswith(folder_path) or folder_path.startswith(path)):
                    return library
        return None


def get_abs_client() -> ABSClient | None:
    abs_url = (config.get("AUDIOBOOKSHELF_URL") or config.get("AUDIOBOOK_LIBRARY_URL") or "").strip()
    abs_key = str(config.get("AUDIOBOOKSHELF_API_KEY") or "").strip()
    if not abs_url or not abs_key:
        return None
    return ABSClient(abs_url, abs_key)


def refresh_library_for_path(file_path: str) -> bool:
    client = get_abs_client()
    if not client:
        return False
    try:
        library = client.find_library_for_path(file_path)
    except ABSError as exc:
        logger.debug("ABS unavailable, skipping library scan: %s", exc)
        return False
    if not library:
        logger.debug("No ABS library found for path: %s", file_path)
        return False
    library_id = library.get("id")
    if not library_id:
        return False
    logger.info("Triggering ABS scan for library: %s", library.get("name", library_id))
    return client.scan_library(library_id)
