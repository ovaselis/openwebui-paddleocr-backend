import logging

from app.config import settings
from app.ocr.base import OCREngine
from app.ocr.mock_engine import MockOCREngine
from app.ocr.paddle_engine import PaddleOCREngine

# Logger for the ocr module
logger = logging.getLogger(__name__)

_engine: OCREngine | None = None #variable to store the engine

def get_engine() -> OCREngine:
    global _engine

    if _engine is not None:
        return _engine #uses the defined variable

    engine_name = settings.ocr_engine.lower().strip() #gets engine name from config

    logger.info("Initializing OCR engine: %s", engine_name)

    #starts an engine based on the name
    if engine_name == "mock":
        _engine = MockOCREngine()
    elif engine_name in {"paddle", "paddleocr"}:
        _engine = PaddleOCREngine()
    else:
        raise ValueError(f"Unsupported OCR engine: {settings.ocr_engine}")

    return _engine


__all__ = ["get_engine"]