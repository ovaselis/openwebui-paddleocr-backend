from pathlib import Path
from typing import Protocol

#defines the common “shape” every OCR engine must have
class OCREngine(Protocol):
    name: str

    async def extract_text(self, image_path: Path) -> tuple[str, float | None]:
        """Return extracted text and optional confidence score."""
        ...
