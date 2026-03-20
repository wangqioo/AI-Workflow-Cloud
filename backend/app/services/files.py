"""File upload/download service.

Ported from v0.7.5 file_transfer_server.py (port 8084).
Cloud mode uses local filesystem; MinIO support planned.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/tmp/ai_workflow_files"))

# Ensure upload directory exists
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Max file size: 100MB
MAX_FILE_SIZE = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "txt", "md", "pdf", "doc", "docx", "xls", "xlsx", "csv", "json", "xml",
    "py", "js", "ts", "html", "css", "yaml", "yml", "toml", "ini", "cfg",
    "sh", "bash", "zsh", "bat", "ps1", "rb", "go", "rs", "java", "c", "cpp", "h",
    "png", "jpg", "jpeg", "gif", "bmp", "svg", "webp",
    "mp3", "wav", "ogg", "flac", "m4a",
    "mp4", "avi", "mkv", "mov", "webm",
    "zip", "tar", "gz", "7z", "rar",
}

MIME_MAP = {
    "txt": "text/plain", "md": "text/markdown", "pdf": "application/pdf",
    "json": "application/json", "xml": "application/xml", "csv": "text/csv",
    "html": "text/html", "css": "text/css",
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp",
    "mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg",
    "mp4": "video/mp4", "zip": "application/zip",
}


def _get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _user_dir(user_id: uuid.UUID) -> Path:
    d = UPLOAD_DIR / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def upload_file(
    user_id: uuid.UUID,
    filename: str,
    content: bytes,
    category: str = "general",
) -> dict:
    """Store an uploaded file on disk."""
    ext = _get_extension(filename)
    if ext and ext not in ALLOWED_EXTENSIONS:
        return {"error": f"File type '.{ext}' not allowed"}

    if len(content) > MAX_FILE_SIZE:
        return {"error": f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)"}

    file_id = uuid.uuid4().hex[:12]
    safe_name = f"{file_id}_{filename.replace('/', '_').replace('..', '_')}"
    user_path = _user_dir(user_id)
    file_path = user_path / safe_name

    file_path.write_bytes(content)

    md5 = hashlib.md5(content).hexdigest()
    mime = MIME_MAP.get(ext, "application/octet-stream")

    # Write metadata
    import json
    meta = {
        "file_id": file_id,
        "filename": filename,
        "stored_name": safe_name,
        "size": len(content),
        "md5": md5,
        "mime_type": mime,
        "category": category,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    meta_path = user_path / f"{file_id}.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False))

    return {
        "file_id": file_id,
        "filename": filename,
        "size": len(content),
        "mime_type": mime,
        "md5": md5,
    }


async def download_file(user_id: uuid.UUID, file_id: str) -> tuple[bytes, str, str] | None:
    """Return (content, filename, mime_type) or None if not found."""
    import json
    user_path = _user_dir(user_id)
    meta_path = user_path / f"{file_id}.meta.json"

    if not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text())
    file_path = user_path / meta["stored_name"]

    if not file_path.exists():
        return None

    return file_path.read_bytes(), meta["filename"], meta["mime_type"]


async def list_files(user_id: uuid.UUID, category: str | None = None) -> list[dict]:
    """List all files for a user."""
    import json
    user_path = _user_dir(user_id)
    files = []

    for meta_file in sorted(user_path.glob("*.meta.json"), reverse=True):
        meta = json.loads(meta_file.read_text())
        if category and meta.get("category") != category:
            continue
        files.append({
            "file_id": meta["file_id"],
            "filename": meta["filename"],
            "size": meta["size"],
            "mime_type": meta["mime_type"],
            "category": meta.get("category", "general"),
            "uploaded_at": meta.get("uploaded_at"),
        })

    return files


async def delete_file(user_id: uuid.UUID, file_id: str) -> bool:
    """Delete a file and its metadata."""
    import json
    user_path = _user_dir(user_id)
    meta_path = user_path / f"{file_id}.meta.json"

    if not meta_path.exists():
        return False

    meta = json.loads(meta_path.read_text())
    file_path = user_path / meta["stored_name"]

    if file_path.exists():
        file_path.unlink()
    meta_path.unlink()
    return True


async def get_stats(user_id: uuid.UUID) -> dict:
    """Get file storage stats for a user."""
    files = await list_files(user_id)
    total_size = sum(f["size"] for f in files)
    by_type: dict[str, int] = {}
    for f in files:
        ext = _get_extension(f["filename"])
        by_type[ext] = by_type.get(ext, 0) + 1

    return {
        "total_files": len(files),
        "total_size": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "by_type": by_type,
    }
