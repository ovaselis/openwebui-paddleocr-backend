import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.config import settings


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def build_cache_key(file_hash: str) -> str:
    config_data = {
        "ocr_engine": settings.ocr_engine,
        "ocr_lang": settings.ocr_lang,
        "ocr_device": settings.ocr_device,
        "ocr_detection_model": settings.ocr_detection_model,
        "ocr_recognition_model": settings.ocr_recognition_model,
        "max_pdf_pages": settings.max_pdf_pages,
        "pdf_dpi": settings.pdf_dpi,
        "pdf_native_text_first": settings.pdf_native_text_first,
        "pdf_native_min_chars": settings.pdf_native_min_chars,
    }

    config_json = json.dumps(config_data, sort_keys=True)
    config_hash = hashlib.sha256(config_json.encode("utf-8")).hexdigest()

    return f"{file_hash}:{config_hash}"


def _connect() -> sqlite3.Connection:
    settings.ocr_cache_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(settings.ocr_cache_path)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ocr_cache (
            cache_key TEXT PRIMARY KEY,
            file_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.commit()

    return connection


def get_cached_response(cache_key: str) -> dict[str, Any] | None:
    if not settings.ocr_cache_enabled:
        return None

    with _connect() as connection:
        row = connection.execute(
            "SELECT response_json FROM ocr_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row[0])


def save_cached_response(
    cache_key: str,
    file_hash: str,
    response_data: dict[str, Any],
) -> None:
    if not settings.ocr_cache_enabled:
        return

    with _connect() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO ocr_cache (cache_key, file_hash, response_json)
            VALUES (?, ?, ?)
            """,
            (
                cache_key,
                file_hash,
                json.dumps(response_data, ensure_ascii=False),
            ),
        )
        connection.commit()
