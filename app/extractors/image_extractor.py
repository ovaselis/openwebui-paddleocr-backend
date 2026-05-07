from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

from app.ocr import get_engine
from app.schemas import OCRPage


def validate_image(path: Path) -> None:
    # checks that uploaded file is a valid image and not just a renamed file
    try:
        with Image.open(path) as image:
            image.verify()

    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file.",
        ) from exc


async def extract_image(path: Path) -> tuple[list[OCRPage], list[str]]:
    # image files are validated and then sent directly to the OCR engine
    validate_image(path)

    text, confidence = await get_engine().extract_text(path)

    pages = [
        OCRPage(
            page=1,
            text=text,
            confidence=confidence,
        )
    ]

    warnings: list[str] = []

    return pages, warnings
