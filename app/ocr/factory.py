from app.config import settings
from app.ocr.base import OCREngine
from app.ocr.mock_engine import MockOCREngine
from app.ocr.paddle_engine import PaddleOCREngine

_engine: OCREngine | None = None


def get_engine() -> OCREngine:
    global _engine
    if _engine is not None:
        return _engine

    engine_name = settings.ocr_engine.lower().strip()
    if engine_name == "mock":
        _engine = MockOCREngine()
    elif engine_name in {"paddle", "paddleocr"}:
        _engine = PaddleOCREngine()
    else:
        raise ValueError(f"Unsupported OCR_ENGINE: {settings.ocr_engine}")

    return _engine
