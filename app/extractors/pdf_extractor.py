import shutil
from pathlib import Path

import fitz
from fastapi import HTTPException, status

from app.config import settings
from app.ocr import get_engine
from app.schemas import OCRPage


async def extract_pdf(pdf_path: Path) -> tuple[list[OCRPage], list[str]]:
    # PDF files are processed page by page.
    # First tries native/selectable PDF text extraction.
    # If page has no useful text, it renders page as image and runs OCR.
    warnings: list[str] = []
    pages: list[OCRPage] = []
    rendered_dir: Path | None = None

    try:
        doc = fitz.open(pdf_path)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted PDF file.",
        ) from exc

    native_pages = 0
    ocr_pages = 0

    try:
        total_pages = doc.page_count

        if total_pages == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF file does not contain any pages.",
            )

        # MAX_PDF_PAGES=0 means process all pages
        if settings.max_pdf_pages <= 0:
            pages_to_process = total_pages
        else:
            pages_to_process = min(total_pages, settings.max_pdf_pages)

            if total_pages > settings.max_pdf_pages:
                warnings.append(
                    f"PDF has {total_pages} pages, but only first "
                    f"{settings.max_pdf_pages} page(s) were processed."
                )

        # PDF DPI is converted to a render zoom factor.
        # 72 DPI is PDF default, so 200 DPI means zoom 200 / 72.
        zoom = settings.pdf_dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for page_index in range(pages_to_process):
            page = doc.load_page(page_index)

            native_text = ""
            if settings.pdf_native_text_first:
                native_text = extract_native_pdf_text(page)

            # If native PDF text has enough meaningful characters, use it.
            # This is faster and more accurate than OCR for digital PDFs.
            if meaningful_char_count(native_text) >= settings.pdf_native_min_chars:
                pages.append(
                    OCRPage(
                        page=page_index + 1,
                        text=native_text,
                        confidence=None,
                    )
                )
                native_pages += 1
                continue

            # If native text is missing or too short, render page to image for OCR.
            if rendered_dir is None:
                rendered_dir = settings.upload_dir / f"{pdf_path.stem}_pages"
                rendered_dir.mkdir(parents=True, exist_ok=True)

            image_path = rendered_dir / f"page_{page_index + 1}.png"
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(image_path)

            text, confidence = await get_engine().extract_text(image_path)

            pages.append(
                OCRPage(
                    page=page_index + 1,
                    text=text,
                    confidence=confidence,
                )
            )
            ocr_pages += 1

        if settings.pdf_native_text_first:
            warnings.append(
                f"PDF extraction mode: native text used for {native_pages} page(s), "
                f"OCR fallback used for {ocr_pages} page(s)."
            )

        return pages, warnings

    finally:
        doc.close()

        # removes temporary rendered PDF page images
        if rendered_dir is not None:
            shutil.rmtree(rendered_dir, ignore_errors=True)


def extract_native_pdf_text(page) -> str:
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


def meaningful_char_count(text: str) -> int:
    """Count meaningful alphanumeric characters to decide if native PDF text is usable."""
    return sum(1 for char in text if char.isalnum())
