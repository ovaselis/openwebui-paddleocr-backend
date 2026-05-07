import logging
from pathlib import Path

from app.cache import (
    build_cache_key,
    get_cached_response,
    save_cached_response,
    sha256_file,
)
from app.config import settings
from app.extractors.docx_extractor import extract_docx
from app.extractors.image_extractor import extract_image
from app.extractors.pdf_extractor import extract_pdf
from app.ocr import get_engine
from app.schemas import OCRResponse


logger = logging.getLogger("paddleocr_backend")


async def process_document(
    saved_path: Path,
    original_name: str,
    suffix: str,
) -> OCRResponse:
    # saves uploaded file's hash
    file_hash = sha256_file(saved_path)

    # saves cache key, including file hash and OCR config
    cache_key = build_cache_key(file_hash)

    cached_response = get_cached_response(cache_key)
    if cached_response is not None:  # checks if file has been processed before
        logger.info("Returning cached OCR result for filename=%s", original_name)
        cached_response["filename"] = original_name

        warnings = cached_response.get("warnings") or []
        warnings.append("Returned cached OCR result; file was not processed again.")
        cached_response["warnings"] = warnings

        return OCRResponse(**cached_response)

    # routes file to the correct extractor depending on file extension
    if suffix == ".pdf":
        file_type = "pdf"
        pages, warnings = await extract_pdf(saved_path)

    elif suffix == ".docx":
        file_type = "docx"
        pages, warnings = await extract_docx(saved_path)

    else:
        file_type = "image"
        pages, warnings = await extract_image(saved_path)

    combined_text = "\n\n".join(  # joins all pages together in one text
        f"## Page {page.page}\n\n{page.text}" for page in pages
    ).strip()

    if not combined_text:  # if the full text is empty throws warning
        warnings.append("OCR completed, but no text was detected.")

    response = OCRResponse(  # makes the JSON OCR response
        filename=original_name,
        file_type=file_type,
        engine=get_engine().name,
        language=settings.ocr_lang,
        page_count=len(pages),
        text=combined_text,
        pages=pages,
        warnings=warnings,
    )

    response_data = (  # turns the response object into a dictionary, so it can be saved in the SQLite cache as JSON
        response.model_dump()
        if hasattr(response, "model_dump")
        else response.dict()
    )

    try:
        save_cached_response(  # saves the OCR result in the SQLite cache
            cache_key=cache_key,
            file_hash=file_hash,
            response_data=response_data,
        )
    except Exception:
        logger.warning("Failed to save OCR cache for %s", original_name, exc_info=True)

    return response
