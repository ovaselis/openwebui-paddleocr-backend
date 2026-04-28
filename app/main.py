import logging
import shutil
import uuid
from docx import Document
from pathlib import Path

import fitz  # PyMuPDF
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.auth import require_api_key
from app.config import settings
from app.ocr.factory import get_engine
from app.schemas import HealthResponse, OCRPage, OCRResponse

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("document_ocr")

app = FastAPI(
    title="Document OCR Backend",
    description="Internal OCR backend for Open WebUI integration.",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("OCR backend started with engine=%s", settings.ocr_engine)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        engine=settings.ocr_engine,
        language=settings.ocr_lang,
        max_file_size_mb=settings.max_file_size_mb,
        max_pdf_pages=settings.max_pdf_pages,
    )


@app.post("/ocr", response_model=OCRResponse, dependencies=[Depends(require_api_key)])
async def ocr_file(file: UploadFile = File(...)) -> OCRResponse:
    original_name = file.filename or "uploaded-file"
    suffix = Path(original_name).suffix.lower()

    if suffix not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(settings.allowed_extensions)}",
        )

    saved_path = await _save_upload(file, suffix)
    logger.info("Received OCR request: filename=%s saved=%s", original_name, saved_path)

    try:
        if suffix == ".pdf":
            pages, warnings = await _ocr_pdf(saved_path)
            file_type = "pdf"

        elif suffix == ".docx":
            file_type = "docx"
            pages, warnings = _extract_docx_text(saved_path)

        else:
            file_type = "image"
            text, confidence = await get_engine().extract_text(saved_path)
            pages = [OCRPage(page=1, text=text, confidence=confidence)]
            warnings = []

        combined_text = "\n\n".join(f"## Page {p.page}\n\n{p.text}" for p in pages).strip()
        if not combined_text:
            warnings.append("OCR completed, but no text was detected.")

        return OCRResponse(
            filename=original_name,
            file_type=file_type,
            engine=get_engine().name,
            language=settings.ocr_lang,
            page_count=len(pages),
            text=combined_text,
            pages=pages,
            warnings=warnings,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("OCR processing failed for %s", original_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR processing failed: {exc}",
        ) from exc


async def _save_upload(file: UploadFile, suffix: str) -> Path:
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    upload_id = uuid.uuid4().hex
    output_path = settings.upload_dir / f"{upload_id}{suffix}"

    total = 0
    with output_path.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                output_path.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File is too large. Max size is {settings.max_file_size_mb} MB.",
                )
            buffer.write(chunk)

    return output_path


def _validate_image(path: Path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file.",
        ) from exc


async def _ocr_pdf(pdf_path: Path) -> tuple[list[OCRPage], list[str]]:
    warnings: list[str] = []
    pages: list[OCRPage] = []
    rendered_dir: Path | None = None

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file.") from exc

    native_pages = 0
    ocr_pages = 0

    try:
        total_pages = doc.page_count

        if total_pages == 0:
            raise HTTPException(
                status_code=400,
                detail="PDF file does not contain any pages.",
            )

        if settings.max_pdf_pages <= 0:
            pages_to_process = total_pages
        else:
            pages_to_process = min(total_pages, settings.max_pdf_pages)

            if total_pages > settings.max_pdf_pages:
                warnings.append(
                    f"PDF has {total_pages} pages, but only first {settings.max_pdf_pages} page(s) were processed."
                )
        zoom = settings.pdf_dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page_index in range(pages_to_process):
            page = doc.load_page(page_index)

            native_text = ""
            if settings.pdf_native_text_first:
                native_text = _extract_native_pdf_text(page)

            if _meaningful_char_count(native_text) >= settings.pdf_native_min_chars:
                pages.append(
                    OCRPage(
                        page=page_index + 1,
                        text=native_text,
                        confidence=None,
                    )
                )
                native_pages += 1
                continue

            if rendered_dir is None:
                rendered_dir = settings.upload_dir / f"{pdf_path.stem}_pages"
                rendered_dir.mkdir(parents=True, exist_ok=True)

            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image_path = rendered_dir / f"page_{page_index + 1}.png"
            pix.save(image_path)

            text, confidence = await get_engine().extract_text(image_path)
            pages.append(OCRPage(page=page_index + 1, text=text, confidence=confidence))
            ocr_pages += 1

        if settings.pdf_native_text_first:
            warnings.append(
                f"PDF extraction mode: native text used for {native_pages} page(s), OCR fallback used for {ocr_pages} page(s)."
            )

        return pages, warnings

    finally:
        doc.close()
        if rendered_dir is not None:
            shutil.rmtree(rendered_dir, ignore_errors=True)

def _extract_native_pdf_text(page) -> str:
    """Extract selectable text from a PDF page using PyMuPDF."""
    try:
        text = page.get_text("text") or ""
    except Exception:
        return ""

    lines: list[str] = []
    previous_blank = False

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            if lines and not previous_blank:
                lines.append("")
            previous_blank = True
            continue

        lines.append(line)
        previous_blank = False

    return "\n".join(lines).strip()


def _meaningful_char_count(text: str) -> int:
    """Count meaningful alphanumeric characters to decide if native PDF text is usable."""
    return sum(1 for char in text if char.isalnum())
def _extract_docx_text(docx_path: Path) -> tuple[list[OCRPage], list[str]]:
    warnings: list[str] = []

    try:
        document = Document(docx_path)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid or corrupted DOCX file.",
        ) from exc

    chunks: list[str] = []

    # Paragraphs
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            chunks.append(text)

    # Tables
    for table_index, table in enumerate(document.tables, start=1):
        chunks.append(f"\n### Table {table_index}\n")

        for row in table.rows:
            cells = []
            for cell in row.cells:
                value = " ".join(
                    p.text.strip()
                    for p in cell.paragraphs
                    if p.text.strip()
                )
                cells.append(value)

            if any(cells):
                chunks.append(" | ".join(cells))

    text = "\n".join(chunks).strip()

    if not text:
        warnings.append("DOCX file did not contain extractable text.")

    return [
        OCRPage(
            page=1,
            text=text,
            confidence=None,
        )
    ], warnings
