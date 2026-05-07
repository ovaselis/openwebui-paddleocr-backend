from typing import Any, Optional, Tuple
from pathlib import Path
import ast
import base64
import json
import mimetypes
import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        OCR_API_URL: str = Field(
            default="http://host.docker.internal:9713/ocr",
            description="Full OCR backend endpoint",
        )
        OCR_API_KEY: str = Field(
            default="",
            description="API key sent as X-API-Key. Do not hardcode production secrets.",
        )
        REQUEST_TIMEOUT_SECONDS: int = Field(
            default=180,
            description="HTTP timeout in seconds",
        )
        DEBUG_MODE: bool = Field(
            default=False,
            description="Return debug details when file extraction fails.",
        )
        OPENWEBUI_UPLOADS_DIR: str = Field(
            default="/app/backend/data/uploads",
            description="Open WebUI uploads directory inside the container.",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def ocr_file_to_text(
        self,
        body: Optional[Any] = None,
        __files__=None,
        __metadata__=None,
        __messages__=None,
        __event_emitter__=None,
    ) -> str:
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Looking for an uploaded file...",
                        "done": False,
                    },
                }
            )

        parsed_body = self._normalize_body(body)

        file_bytes, filename, content_type, debug_info = self._extract_file(
            parsed_body=parsed_body,
            files_list=__files__ or [],
            metadata=__metadata__ or {},
            messages=__messages__ or [],
        )

        if file_bytes is None:
            if self.valves.DEBUG_MODE:
                return f"DEBUG: no supported file found.\n{debug_info}"
            return "No supported file was found. Please attach a supported image, PDF, or DOCX file and try again."

        headers = {}
        if self.valves.OCR_API_KEY:
            headers["X-API-Key"] = self.valves.OCR_API_KEY

        files = {
            "file": (
                filename,
                file_bytes,
                content_type or "application/octet-stream",
            )
        }

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Sending file to OCR backend...",
                        "done": False,
                    },
                }
            )

        try:
            response = requests.post(
                self.valves.OCR_API_URL,
                headers=headers,
                files=files,
                timeout=self.valves.REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as e:
            return f"Failed to reach OCR backend: {e}"

        if response.status_code != 200:
            return f"OCR backend returned {response.status_code}: {response.text}"

        try:
            data = response.json()
        except ValueError:
            return "OCR backend returned a non-JSON response."

        text = self._pick_text_from_response(data)
        if not text:
            return "The text was not recognized."

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "OCR complete.", "done": True},
                }
            )

        return text

    def _normalize_body(self, body: Any) -> dict:
        if body is None:
            return {}

        if isinstance(body, dict):
            return body

        if isinstance(body, str):
            body = body.strip()
            if not body:
                return {}

            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

            try:
                parsed = ast.literal_eval(body)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

        return {}

    def _pick_text_from_response(self, data: Any) -> str:
        if isinstance(data, dict):
            if isinstance(data.get("text"), str) and data.get("text").strip():
                return data["text"].strip()

            pages = data.get("pages")
            if isinstance(pages, list):
                chunks = []
                for page in pages:
                    if isinstance(page, dict):
                        value = page.get("text") or page.get("markdown")
                        if isinstance(value, str) and value.strip():
                            chunks.append(value.strip())
                if chunks:
                    return "\n\n".join(chunks)

        return ""

    def _extract_file(
        self,
        parsed_body: dict,
        files_list: list,
        metadata: dict,
        messages: list,
    ) -> Tuple[Optional[bytes], str, Optional[str], str]:
        debug = []

        debug.append(f"__files__ count={len(files_list)}")
        for idx, item in enumerate(files_list):
            file_bytes, filename, content_type, info = (
                self._read_supported_file_from_entry(item)
            )
            debug.append(f"__files__[{idx}] -> {info}")
            if file_bytes is not None:
                return file_bytes, filename, content_type, "\n".join(debug)

        metadata_files = []
        if isinstance(metadata, dict):
            metadata_files = metadata.get("files", []) or []
        debug.append(f"__metadata__.files count={len(metadata_files)}")

        for idx, item in enumerate(metadata_files):
            file_bytes, filename, content_type, info = (
                self._read_supported_file_from_metadata(item)
            )
            debug.append(f"__metadata__.files[{idx}] -> {info}")
            if file_bytes is not None:
                return file_bytes, filename, content_type, "\n".join(debug)

        body_files = (
            parsed_body.get("files", []) if isinstance(parsed_body, dict) else []
        )
        debug.append(f'body["files"] count={len(body_files)}')

        for idx, item in enumerate(body_files):
            file_bytes, filename, content_type, info = (
                self._read_supported_file_from_metadata(item)
            )
            debug.append(f'body["files"][{idx}] -> {info}')
            if file_bytes is not None:
                return file_bytes, filename, content_type, "\n".join(debug)

        debug.append(f"__messages__ count={len(messages)}")
        for midx, message in enumerate(messages):
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue

            for pidx, part in enumerate(content):
                if not isinstance(part, dict):
                    continue

                if part.get("type") == "image_url":
                    image_obj = part.get("image_url")
                    candidate = (
                        image_obj.get("url")
                        if isinstance(image_obj, dict)
                        else image_obj
                    )
                    if isinstance(candidate, str) and candidate.startswith("data:"):
                        file_bytes, filename, content_type, info = self._read_data_url(
                            candidate,
                            fallback_filename="upload.png",
                        )
                        debug.append(f"__messages__[{midx}].content[{pidx}] -> {info}")
                        if file_bytes is not None:
                            return file_bytes, filename, content_type, "\n".join(debug)

        return None, "upload.bin", None, "\n".join(debug)

    def _read_supported_file_from_entry(
        self, item: Any
    ) -> Tuple[Optional[bytes], str, Optional[str], str]:
        if not isinstance(item, dict):
            return None, "upload.bin", None, "entry is not dict"

        file_info = item.get("file") if isinstance(item.get("file"), dict) else item
        path_value = file_info.get("path")
        filename = file_info.get("filename") or file_info.get("name") or "upload.bin"
        content_type = file_info.get("content_type")

        if not path_value:
            return None, filename, content_type, "no path in __files__ entry"

        path = Path(path_value)
        if not path.exists() or not path.is_file():
            return None, filename, content_type, f"path not found: {path_value}"

        guessed_type, _ = mimetypes.guess_type(str(path))
        final_type = content_type or guessed_type
        suffix = path.suffix.lower()

        if self._is_supported_type(final_type, suffix):
            return (
                path.read_bytes(),
                filename,
                final_type,
                f"loaded from __files__ path: {path_value}",
            )

        return (
            None,
            filename,
            content_type,
            f"unsupported __files__ type: {suffix} / {final_type}",
        )

    def _read_supported_file_from_metadata(
        self, item: Any
    ) -> Tuple[Optional[bytes], str, Optional[str], str]:
        if not isinstance(item, dict):
            return None, "upload.bin", None, "metadata item is not dict"

        file_id = item.get("id") or item.get("file_id")
        filename = item.get("filename") or item.get("name") or "upload.bin"
        content_type = item.get("content_type")

        if not file_id:
            return None, filename, content_type, "no file id in metadata"

        uploads_dir = Path(self.valves.OPENWEBUI_UPLOADS_DIR)
        candidate_path = uploads_dir / f"{file_id}_{filename}"

        if candidate_path.exists() and candidate_path.is_file():
            guessed_type, _ = mimetypes.guess_type(str(candidate_path))
            final_type = content_type or guessed_type
            suffix = candidate_path.suffix.lower()

            if self._is_supported_type(final_type, suffix):
                return (
                    candidate_path.read_bytes(),
                    filename,
                    final_type or "application/octet-stream",
                    f"loaded from metadata path: {candidate_path}",
                )

            return (
                None,
                filename,
                content_type,
                f"metadata file exists but unsupported type: {suffix} / {final_type}",
            )

        return (
            None,
            filename,
            content_type,
            f"metadata path not found: {candidate_path}",
        )

    def _read_data_url(
        self, value: str, fallback_filename: str = "upload.bin"
    ) -> Tuple[Optional[bytes], str, Optional[str], str]:
        try:
            header, encoded = value.split(",", 1)
            mime = header.split(";", 1)[0].replace("data:", "") or None
            data = base64.b64decode(encoded)
            extension = mimetypes.guess_extension(mime or "") or ".bin"
            filename = fallback_filename
            if filename == "upload.bin":
                filename = f"upload{extension}"
            return data, filename, mime, "loaded from data URL in __messages__"
        except Exception as e:
            return None, fallback_filename, None, f"failed to decode data URL: {e}"

    def _is_supported_type(self, content_type: Optional[str], suffix: str) -> bool:
        supported_suffixes = {
            ".pdf",
            ".png",
            ".docx",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".tiff",
            ".tif",
        }

        if content_type == "application/pdf":
            return True

        if (
            content_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return True

        if content_type and content_type.startswith("image/"):
            return True

        if suffix.lower() in supported_suffixes:
            return True

        return False
