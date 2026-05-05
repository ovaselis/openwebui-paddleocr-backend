"""FastAPI entry point for the OCR backend.

This file only defines HTTP endpoints and request-level error handling.
The actual OCR logic is delegated to service and extractor modules.
"""

import logging

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status

from app.auth import require_api_key
from app.config import settings
from app.schemas import HealthResponse, OCRResponse
from app.services.file_service import (
    get_file_suffix,
    save_upload,
    validate_file_extension,
)
from app.services.ocr_service import process_document


# logger configuration
logger = logging.getLogger("paddleocr_backend")

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)


# creates FastAPI app
app = FastAPI(
    title="OpenWebUI PaddleOCR Backend",
    description="OCR and document text extraction backend for Open WebUI.",
    version="0.1.0",
)


# when backend starts
@app.on_event("startup")
async def startup_event() -> None:
    # creates upload directory for uploaded files
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("OCR backend started with engine=%s", settings.ocr_engine)


# GET /health endpoint, returns base config of the OCR backend
@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        engine=settings.ocr_engine,
        language=settings.ocr_lang,
        max_file_size_mb=settings.max_file_size_mb,
        max_pdf_pages=settings.max_pdf_pages,
    )


# POST /ocr endpoint
@app.post("/ocr", response_model=OCRResponse, dependencies=[Depends(require_api_key)])  # checks API key
async def ocr_file(file: UploadFile = File(...)) -> OCRResponse:
    original_name = file.filename or "uploaded-file"  # file upload name
    suffix = get_file_suffix(original_name)  # gets the extension, for example ".pdf", ".png", ".docx"

    validate_file_extension(suffix)  # checks if file type is allowed

    saved_path = await save_upload(file, suffix)  # saves uploaded file in temporary dir
    logger.info("Received OCR request: filename=%s saved=%s", original_name, saved_path)

    try:
        return await process_document(
            saved_path=saved_path,
            original_name=original_name,
            suffix=suffix,
        )

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("OCR processing failed for %s", original_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR processing failed: {exc}",
        ) from exc

    finally:
        try:
            saved_path.unlink(missing_ok=True)
        except Exception:
            logger.warning("Could not remove uploaded file: %s", saved_path)
            logger.warning("Could not remove uploaded file: %s", saved_path)
