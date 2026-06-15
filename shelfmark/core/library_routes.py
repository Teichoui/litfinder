"""Library file-management API routes.

Server-agnostic file operations (list, rename, mkdir, move, organize) scoped to
the folders configured in LIBRARY_FOLDERS. Works for any library server's folders
(Calibre, Calibre-Web, Audiobookshelf, etc.) — it only ever touches paths inside
a configured library folder.
"""

from __future__ import annotations

import contextlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flask import Flask, Response, jsonify, request, session

from shelfmark.core.logger import setup_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = setup_logger(__name__)


def _resolve_conflict(path: Path) -> Path:
    """Return a non-conflicting path by appending (1), (2), etc."""
    if not path.exists():
        return path
    stem, suffix, parent = path.stem, path.suffix, path.parent
    counter = 1
    candidate = parent / f"{stem} ({counter}){suffix}"
    while candidate.exists():
        counter += 1
        candidate = parent / f"{stem} ({counter}){suffix}"
    return candidate


def _allowed_folder_roots() -> set[Path]:
    """Return the resolved paths of all configured library folders."""
    from shelfmark.core.utils import get_library_folders

    roots: set[Path] = set()
    for f in get_library_folders():
        with contextlib.suppress(OSError, ValueError):
            roots.add(Path(f["path"]).resolve())
    return roots


def _is_within_allowed(path: Path, allowed: set[Path]) -> bool:
    """Return True if path is within (or equal to) any allowed directory."""
    if not allowed:
        return False
    try:
        resolved = path.resolve()
        return any(resolved == a or resolved.is_relative_to(a) for a in allowed)
    except OSError, ValueError:
        return False


def register_library_routes(app: Flask, *, resolve_auth_mode: Callable[[], str]) -> None:
    """Register library file-management routes on the Flask app."""

    def _require_auth(action: str) -> tuple[Response, int] | None:
        if resolve_auth_mode() == "none":
            return None
        if "user_id" not in session:
            return jsonify({"error": "Unauthorized", "action": action}), 401
        return None

    @app.route("/api/library-folders", methods=["GET"])
    def api_library_folders() -> Response | tuple[Response, int]:
        if (gate := _require_auth("browse")) is not None:
            return gate
        from shelfmark.core.utils import get_library_folders

        return jsonify(get_library_folders())

    @app.route("/api/library/move-file", methods=["POST"])
    def api_library_move_file() -> Response | tuple[Response, int]:
        if (gate := _require_auth("move")) is not None:
            return gate

        data = request.get_json(silent=True) or {}
        source_path = str(data.get("source_path") or "").strip()
        destination_path = str(data.get("destination_path") or "").strip()

        if not source_path or not destination_path:
            return jsonify({"error": "source_path and destination_path required"}), 400

        source = Path(source_path)
        if not source.exists():
            return jsonify({"error": "Source file does not exist"}), 404

        allowed = _allowed_folder_roots()
        if not _is_within_allowed(source, allowed):
            return jsonify({"error": "Source path is not within a configured library folder"}), 403
        dest_path = Path(destination_path)
        if not _is_within_allowed(dest_path.parent if dest_path.suffix else dest_path, allowed):
            return jsonify({"error": "Destination is not within a configured library folder"}), 403

        try:
            dest = _resolve_conflict(dest_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))
        except (OSError, shutil.Error) as exc:
            return jsonify({"error": f"Failed to move file: {exc}"}), 500

        logger.info("Moved file: %s -> %s", source_path, dest)
        return jsonify({"success": True, "new_path": str(dest)})

    @app.route("/api/library/organize", methods=["POST"])
    def api_library_organize() -> Response | tuple[Response, int]:
        if (gate := _require_auth("organize")) is not None:
            return gate

        data = request.get_json(silent=True) or {}
        files: list[Any] = data.get("files") or []
        target_folder = str(data.get("target_folder") or "").strip()

        if not files or not target_folder:
            return jsonify({"error": "files and target_folder required"}), 400

        dest_dir = Path(target_folder)
        allowed = _allowed_folder_roots()
        if not _is_within_allowed(dest_dir, allowed):
            return jsonify(
                {"error": "target_folder is not within a configured library folder"}
            ), 403

        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return jsonify({"error": f"Cannot create target folder: {exc}"}), 500

        moved: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []

        for file_info in files:
            source_path = str(file_info.get("path") or "").strip()
            if not source_path:
                continue

            source = Path(source_path)
            if not source.exists():
                failed.append({"path": source_path, "error": "File not found"})
                continue

            if not _is_within_allowed(source, allowed):
                failed.append(
                    {"path": source_path, "error": "Not within a configured library folder"}
                )
                continue

            try:
                dest = _resolve_conflict(dest_dir / source.name)
                shutil.move(str(source), str(dest))
                moved.append({"original_path": source_path, "new_path": str(dest)})
            except (OSError, shutil.Error) as exc:
                logger.exception("Failed to move %s", source_path)
                failed.append({"path": source_path, "error": str(exc)})

        return jsonify(
            {
                "success": len(failed) == 0,
                "moved_files": moved,
                "failed_files": failed,
                "summary": f"Moved {len(moved)}, failed {len(failed)}",
            }
        )

    @app.route("/api/library/ls", methods=["GET"])
    def api_library_ls() -> Response | tuple[Response, int]:
        if (gate := _require_auth("browse")) is not None:
            return gate

        folder_path = str(request.args.get("path") or "").strip()
        if not folder_path:
            return jsonify({"error": "path required"}), 400

        folder = Path(folder_path)
        if not folder.is_dir():
            return jsonify({"error": "Path does not exist or is not a directory"}), 404

        allowed = _allowed_folder_roots()
        if not _is_within_allowed(folder, allowed):
            return jsonify({"error": "Path is not within a configured library folder"}), 403

        try:
            entries = []
            # Dirs first, then files, both sorted case-insensitively
            items = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            for item in items:
                try:
                    stat = item.stat()
                except OSError:
                    continue
                entry: dict[str, Any] = {
                    "name": item.name,
                    "path": str(item),
                    "type": "file" if item.is_file() else "dir",
                    "modified": stat.st_mtime,
                }
                if item.is_file():
                    entry["size"] = stat.st_size
                    entry["extension"] = item.suffix.lower()
                entries.append(entry)
            return jsonify({"path": folder_path, "entries": entries})
        except OSError as exc:
            logger.exception("Failed to list directory %s", folder_path)
            return jsonify({"error": f"Failed to list directory: {exc}"}), 500

    @app.route("/api/library/rename", methods=["POST"])
    def api_library_rename() -> Response | tuple[Response, int]:
        if (gate := _require_auth("rename")) is not None:
            return gate

        data = request.get_json(silent=True) or {}
        path_str = str(data.get("path") or "").strip()
        new_name = str(data.get("new_name") or "").strip()

        if not path_str or not new_name:
            return jsonify({"error": "path and new_name required"}), 400

        if "/" in new_name or "\\" in new_name or "\x00" in new_name or new_name in (".", ".."):
            return jsonify({"error": "new_name must be a plain filename, not a path"}), 400

        src = Path(path_str)
        if not src.exists():
            return jsonify({"error": "Path does not exist"}), 404

        allowed = _allowed_folder_roots()
        if not _is_within_allowed(src, allowed):
            return jsonify({"error": "Path is not within a configured library folder"}), 403

        dest = src.parent / new_name
        if dest.exists():
            return jsonify({"error": "A file or folder with that name already exists"}), 409

        try:
            src.rename(dest)
        except OSError as exc:
            return jsonify({"error": f"Rename failed: {exc}"}), 500

        logger.info("Renamed: %s -> %s", src, dest)
        return jsonify({"success": True, "new_path": str(dest)})

    @app.route("/api/library/mkdir", methods=["POST"])
    def api_library_mkdir() -> Response | tuple[Response, int]:
        if (gate := _require_auth("mkdir")) is not None:
            return gate

        data = request.get_json(silent=True) or {}
        parent_path = str(data.get("parent_path") or "").strip()
        name = str(data.get("name") or "").strip()

        if not parent_path or not name:
            return jsonify({"error": "parent_path and name required"}), 400

        if "/" in name or "\\" in name or "\x00" in name or name in (".", ".."):
            return jsonify({"error": "name must be a plain folder name, not a path"}), 400

        parent = Path(parent_path)
        if not parent.is_dir():
            return jsonify({"error": "Parent directory does not exist"}), 404

        allowed = _allowed_folder_roots()
        if not _is_within_allowed(parent, allowed):
            return jsonify({"error": "Parent is not within a configured library folder"}), 403

        new_dir = parent / name
        if new_dir.exists():
            return jsonify({"error": "A file or folder with that name already exists"}), 409

        try:
            new_dir.mkdir(parents=False)
        except OSError as exc:
            return jsonify({"error": f"Failed to create directory: {exc}"}), 500

        logger.info("Created directory: %s", new_dir)
        return jsonify({"success": True, "path": str(new_dir)})
