from typing import Any

from app.config import settings

_engine: Any | None = None


def get_engine() -> Any:
    global _engine

    if _engine is not None:
        return _engine

    engine_name = settings.ocr_engine.lower().strip()

    if engine_name == "mock":
        from app.ocr.mock_engine import MockOCREngine

        _engine = MockOCREngine()
        return _engine

    if engine_name == "paddleocr":
        from app.ocr.paddle_engine import PaddleOCREngine

        _engine = PaddleOCREngine()
        return _engine

    raise RuntimeError(
        f"Unsupported OCR_ENGINE='{settings.ocr_engine}'. "
        "Supported engines: mock, paddleocr."
    )
